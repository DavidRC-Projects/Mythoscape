"""Preview sheets composed from the rendered layers exactly as the runtime would (z-order + tint)."""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/workspace/player_hd/src")
from pl_post import split, to_img
RAW = "/workspace/player_hd/renders"
PV = "/workspace/player_hd/previews"; os.makedirs(PV, exist_ok=True)
CAT = json.load(open("/workspace/player_hd/assets/catalogue.json"))
Z = {it["layer"]: it["z"] for it in CAT["items"]}
Z.update({a["layer"]: a["z"] for a in CAT["armour_layers"]}); Z.update({w["layer"]: w["z"] for w in CAT["weapon_layers"]})
Z["shadow"] = {"s": 0, "e": 0, "n": 0, "w": 0}; Z["brows"] = {"s": 12, "e": 12, "n": 12, "w": 12}
PAL = {p["id"]: tuple(c / 255 for c in p["mul"]) for p in CAT["hair_palette"]}
TIER = {k: tuple(min(1.0, c / 255 * CAT["tier_tint_gain"]) for c in v) for k, v in CAT["tier_tints"].items()}
try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
except Exception:
    FONT = FONT_B = ImageFont.load_default()
_cache = {}


def layer_frame(kind, scale, lid, anim, face, k):
    key = (kind, scale, lid, anim, face, k)
    if key not in _cache:
        f = "e" if face == "w" else face
        p = f"{RAW}/{kind}/{scale}/{lid}/{anim}_{f}_{k:02d}.png"
        if not os.path.exists(p):
            _cache[key] = None
        else:
            fx, tn = split(p)
            if face == "w":
                fx = fx[:, ::-1]; tn = tn[:, ::-1] if tn is not None else None
            _cache[key] = (fx, tn)
    return _cache[key]


def compose(kind, scale, look, anim="idle", face="s", k=0, hair="dark_brown", tier="steel", bg=None):
    W, H = (288, 288) if scale == "2x" else (576, 576)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0) if bg is None else bg + (255,))
    layers = ["shadow"] + list(look)
    layers.sort(key=lambda l: Z.get(l, {"s": 50, "e": 50, "n": 50, "w": 50})[face])
    for lid in layers:
        fr = layer_frame(kind, scale, lid, anim, face, k)
        if fr is None:
            continue
        fx, tn = fr
        out.alpha_composite(to_img(fx))
        if tn is not None:
            col = PAL[hair] if (lid.startswith("hair") or lid == "brows") else TIER[tier]
            out.alpha_composite(to_img(tn * np.array(col + (1.0,), np.float32)))
    return out


def resolve(kind, look):
    """Apply the catalogue override rules to a dict look -> layer list (mirrors what the client must do)."""
    L = [f"body_{look.get('skin', 'light')}", "brows"]
    arm = look.get("armour", [])
    body_arm = any(a in ("arm_platebody", "arm_chainbody") for a in arm)
    legs_arm = "arm_platelegs" in arm
    if "arm_helm" not in arm and look.get("hair"):
        L.append(look["hair"])
    outfit = look.get("outfit") if not (body_arm or legs_arm) else None
    if outfit:
        L.append(outfit)
    else:
        if not body_arm and look.get("top"):
            L.append(look["top"])
        if not legs_arm and look.get("bottom"):
            L.append(look["bottom"])
    if "arm_platebody" in arm:
        arm = arm + ["arm_gauntlets"]
    if legs_arm:
        arm = arm + ["arm_sabatons"]
    elif look.get("shoes"):
        L.append(look["shoes"])
    for a in look.get("acc", []):
        if a == "acc_leather_gloves" and "arm_gauntlets" in arm:
            continue
        L.append(a)
    L += arm + look.get("wpn", [])
    return L


D = CAT["defaults"]


def starter(kind, **over):
    d = dict(skin="light", hair=D[kind]["hair"], top=D[kind]["top"], bottom=D[kind]["bottom"], shoes=D[kind]["shoes"], acc=[], armour=[], wpn=[])
    d.update(over)
    return d


def crop(im, scale):
    if scale == "4x":
        return im.crop((168, 130, 408, 516))
    return im.crop((64, 65, 224, 258))


def label(im, text, font=FONT):
    c = Image.new("RGBA", (im.width, im.height + 22), (0, 0, 0, 0)); c.alpha_composite(im, (0, 22))
    ImageDraw.Draw(c).text((4, 2), text, fill=(20, 20, 20, 255), font=font)
    return c


def grid(tiles, cols, bg=(160, 160, 160), title=None, pad=6):
    w = max(t.width for t in tiles); h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    top = 40 if title else 0
    sheet = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad) + pad + top), bg + (255,))
    if title:
        ImageDraw.Draw(sheet).text((pad, 8), title, fill=(15, 15, 15, 255), font=FONT_B)
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, (pad + (i % cols) * (w + pad), top + pad + (i // cols) * (h + pad)))
    return sheet


def creator_sheet():
    tiles = []
    for kind in ("male", "female"):
        for sk in ("light", "tan", "deep"):
            tiles.append(label(crop(compose("male" if kind == "male" else "female", "4x", resolve(kind, starter(kind, skin=sk))), "4x"), f"{kind} {sk}"))
    hair_cols = ["black", "dark_brown", "chestnut", "copper", "blonde", "ash_grey", "azure", "rose"]
    for kind in ("male", "female"):
        for i, it in enumerate([x for x in CAT["items"] if x["slot"] == "hair"]):
            col = hair_cols[(i + (3 if kind == "female" else 0)) % len(hair_cols)]
            tiles.append(label(crop(compose(kind, "4x", resolve(kind, starter(kind, hair=it["id"])), hair=col), "4x"),
                               f"{it['name']} ({col}) {'free' if it['starter'] else str(it['price']) + 'c'}"))
    for slot in ("top", "bottom", "shoes", "outfit", "accessory"):
        for kind in ("male", "female"):
            for it in [x for x in CAT["items"] if x["slot"] == slot]:
                look = starter(kind)
                if slot == "accessory":
                    look["acc"] = [it["id"]]
                else:
                    look[slot] = it["id"]
                face = "e" if it["id"] in ("acc_travel_cloak", "acc_satchel") else "s"
                tiles.append(label(crop(compose(kind, "4x", resolve(kind, look), face=face, hair=D[kind]["hair_colour"]), "4x"),
                                   f"{it['name'][:20]} {'free' if it['starter'] else str(it['price']) + 'c'}"))
    sheet = grid(tiles, 12, title="Mythoscape HD player - creator / salon / shop options (4x preview layers, composed like the runtime)")
    # hair palette swatches
    sw = Image.new("RGBA", (sheet.width, 60), (160, 160, 160, 255)); d = ImageDraw.Draw(sw)
    for i, p in enumerate(CAT["hair_palette"]):
        x = 10 + i * 150
        d.rectangle((x, 10, x + 40, 50), fill=tuple(p["mul"]) + (255,)); d.text((x + 46, 22), p["id"], fill=(10, 10, 10, 255), font=FONT)
    out = Image.new("RGBA", (sheet.width, sheet.height + 60)); out.alpha_composite(sheet); out.alpha_composite(sw, (0, sheet.height))
    out.convert("RGB").save(f"{PV}/creator_options_contact_sheet.png", optimize=True)
    print("creator sheet", out.size)


LOOKS = {
    "male": [("Starter (free)", starter("male"), "dark_brown", "steel"),
             ("Noble doublet + cloak", starter("male", hair="hair_shoulder_wavy", top="top_noble_doublet", bottom="bottom_noble_hose", shoes="shoes_riding_boots", acc=["acc_travel_cloak"]), "black", "steel"),
             ("Hunter outfit + satchel", starter("male", skin="deep", hair="hair_crop", outfit="outfit_hunter", shoes="shoes_riding_boots", acc=["acc_satchel"], wpn=["wpn_bow"]), "black", "steel"),
             ("Bronze armour", starter("male", skin="tan", armour=["arm_helm", "arm_platebody", "arm_platelegs", "arm_kiteshield"], wpn=["wpn_sword"]), "dark_brown", "bronze"),
             ("Steel plate", starter("male", armour=["arm_helm", "arm_platebody", "arm_platelegs", "arm_kiteshield"], wpn=["wpn_sword"]), "dark_brown", "steel"),
             ("Mithril chain + cosmetic top hidden", starter("male", hair="hair_braid", armour=["arm_chainbody", "arm_platelegs"], wpn=["wpn_axe"]), "copper", "mithril")],
    "female": [("Starter (free)", starter("female"), "chestnut", "steel"),
               ("Noble gown", starter("female", skin="deep", hair="hair_long_straight", outfit="outfit_noble"), "black", "steel"),
               ("Mage robe + scarf", starter("female", skin="tan", hair="hair_braid", outfit="outfit_mage_robe", acc=["acc_scarf"], wpn=["wpn_staff"]), "blonde", "wood"),
               ("Bronze armour", starter("female", skin="tan", armour=["arm_helm", "arm_platebody", "arm_platelegs", "arm_kiteshield"], wpn=["wpn_sword"]), "chestnut", "bronze"),
               ("Steel plate", starter("female", armour=["arm_helm", "arm_platebody", "arm_platelegs", "arm_kiteshield"], wpn=["wpn_sword"]), "chestnut", "steel"),
               ("Adamant legs + jerkin", starter("female", hair="hair_shoulder_wavy", top="top_leather_jerkin", armour=["arm_platelegs"], acc=["acc_leather_gloves"], wpn=["wpn_pickaxe"]), "auburn", "adamant")],
}


def outfits_sheet():
    for kind in ("male", "female"):
        tiles = []
        for name, look, hair, tier in LOOKS[kind]:
            for face in ("s", "e", "n", "w"):
                tiles.append(label(crop(compose(kind, "4x", resolve(kind, look), face=face, hair=hair, tier=tier), "4x"), f"{name[:24]} {face}" if face == "s" else face))
        g = grid(tiles, 8, title=f"{kind}: composed outfits & armour tiers, 4 facings (w = mirrored e)")
        g.convert("RGB").save(f"{PV}/outfits_{kind}_4facings.png", optimize=True)
        print("outfits", kind, g.size)


def anim_sheet():
    rows = []
    for kind, look, hair, tier in (("male", LOOKS["male"][4][1], "dark_brown", "steel"), ("female", LOOKS["female"][0][1], "chestnut", "steel"),
                                   ("female", LOOKS["female"][3][1], "chestnut", "bronze")):
        L = resolve(kind, look)
        for anim, face, n in (("idle", "s", 8), ("walk", "s", 8), ("walk", "e", 8), ("walk", "n", 8), ("melee", "e", 10)):
            tiles = [crop(compose(kind, "2x", L, anim, face, k, hair=hair, tier=tier, bg=(150, 150, 150)), "2x") for k in range(n)]
            rows.append(label(grid(tiles, 10, bg=(150, 150, 150), pad=0), f"{kind} {anim} {face} (2x game sprites)"))
    for kind, extra, anim in (("male", ["wpn_bow"], "ranged"), ("male", ["wpn_axe"], "chop"), ("female", ["wpn_pickaxe"], "mine"), ("female", ["wpn_rod"], "fish")):
        L = resolve(kind, starter(kind, wpn=extra))
        tiles = [crop(compose(kind, "2x", L, anim, "e", k, hair=D[kind]["hair_colour"], tier="iron" if anim != "ranged" else "wood", bg=(150, 150, 150)), "2x") for k in range(8)]
        rows.append(label(grid(tiles, 10, bg=(150, 150, 150), pad=0), f"{kind} {anim} e (2x)"))
    g = grid(rows, 1, title="2x in-game sprite frames (actual game scale x1; tile = 80 px at 2x)")
    g.convert("RGB").save(f"{PV}/anim_frames_2x.png", optimize=True)
    print("anim", g.size)


def hero_lineup():
    hd = "/workspace/player_hd/work/hero"
    order = ["male_starter", "female_starter", "male_noble", "female_noble", "male_ranger", "female_mage", "male_steel", "female_bronze"]
    ims = [Image.open(f"{hd}/{n}.png").convert("RGBA") for n in order if os.path.exists(f"{hd}/{n}.png")]
    if not ims:
        return
    ims = [im.crop((150, 80, 850, 1500)) for im in ims]
    W = sum(im.width for im in ims) - 180 * (len(ims) - 1)
    bg = Image.new("RGBA", (W, ims[0].height), (128, 128, 130, 255))
    g = np.linspace(0, 1, bg.height)[:, None]
    arr = np.asarray(bg).astype(np.float32); arr[..., :3] = (arr[..., :3] * (1.08 - 0.16 * g[..., None]))
    bg = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
    x = 0
    for im in ims:
        bg.alpha_composite(im, (x, 0)); x += im.width - 180
    bg = bg.resize((bg.width * 2 // 3, bg.height * 2 // 3), Image.LANCZOS)
    bg.convert("RGB").save(f"{PV}/hero_lineup_grey.png", optimize=True)
    print("hero", bg.size)


if __name__ == "__main__":
    what = sys.argv[1:] or ["creator", "outfits", "anim", "hero"]
    if "creator" in what: creator_sheet()
    if "outfits" in what: outfits_sheet()
    if "anim" in what: anim_sheet()
    if "hero" in what: hero_lineup()
