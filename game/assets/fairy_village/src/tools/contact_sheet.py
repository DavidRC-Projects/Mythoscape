import os, glob, json
from PIL import Image, ImageDraw, ImageFont
F = "/workspace/fairy_village"; A = F + "/assets"
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
CW = 520
heroes = [("buildings", k) for k in ("queens_tree_hall", "moonpetal_inn", "mushroom_apothecary")] + [("fountains", k) for k in ("moonstone_fountain", "lily_fountain")] + \
         [("npcs", k) for k in ("elowen_moonwhisper", "warden_thorne", "tumbleroot", "pip_dewdrop")]
cells = []
for kind, k in heroes:
    p = f"{A}/{kind}/{k}/{k}_hero_2048_bg.jpg"
    if os.path.exists(p):
        cells.append((k, Image.open(p).resize((CW, CW), Image.LANCZOS)))
p = f"{A}/npcs/elowen_moonwhisper/portrait_bust_bg.jpg"
if os.path.exists(p):
    cells.append(("elowen portrait (dialogue)", Image.open(p).resize((CW, CW), Image.LANCZOS)))
cols = 5
rows = (len(cells) + cols - 1) // cols
moss = Image.open(f"{A}/tiles/fairy_moss_v1_80.png")
# sprite strip at 2x on moss
strip_h = 760
W = cols * CW + (cols + 1) * 12
H = 80 + rows * (CW + 50) + strip_h + 330 + 420
sheet = Image.new("RGB", (W, H), (18, 20, 28)); d = ImageDraw.Draw(sheet)
d.text((16, 20), "Mythoscape · Fairy Village (Moonpetal Glade) asset pack: hero renders, game sprites, animation, tiles", font=font, fill=(255, 230, 160))
for i, (name, im) in enumerate(cells):
    x = 12 + (i % cols) * (CW + 12); y = 80 + (i // cols) * (CW + 50)
    sheet.paste(im, (x, y)); d.text((x, y + CW + 8), name, font=small, fill=(220, 220, 230))
y0 = 80 + rows * (CW + 50)
bg = Image.new("RGBA", (W - 24, strip_h - 40))
for tx in range(0, bg.width, 80):
    for ty in range(0, bg.height, 80):
        bg.paste(moss, (tx, ty))
x = 20
for kind, k in heroes:
    d0 = f"{A}/{kind}/{k}"
    if not os.path.exists(f"{d0}/meta.json"):
        continue
    m = json.load(open(f"{d0}/meta.json"))
    if kind == "npcs":
        continue
    else:
        p = f"{d0}/{m['files']['2x']}" if "frames" not in m else f"{d0}/frames_2x/f00.png"
        im = Image.open(p).convert("RGBA")
        sc = min(1.0, (bg.height - 20) / im.height)
        if sc < 1:
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        if x + im.width > bg.width:
            continue
        bg.alpha_composite(im, (x, bg.height - im.height - 10)); x += im.width + 10
sheet.paste(bg.convert("RGB"), (12, y0 + 30))
d.text((16, y0), "In-game sprites (2x = 80 px/tile; NPCs show the s/e/n/w idle facings)", font=small, fill=(220, 220, 230))
yn = y0 + strip_h
d.text((16, yn), "NPC idle sprites at 2x, facings s / e / n / w (Elowen, Thorne, Tumbleroot, Pip)", font=small, fill=(220, 220, 230))
nb = Image.new("RGBA", (W - 24, 290))
for tx in range(0, nb.width, 80):
    for ty in range(0, nb.height, 80):
        nb.paste(moss, (tx, ty))
x = 10
for kind, k in heroes:
    if kind != "npcs":
        continue
    for f in ("s", "e", "n", "w"):
        p = f"{A}/npcs/{k}/sprite_2x/{f}/f00.png"
        if os.path.exists(p):
            im = Image.open(p).convert("RGBA"); nb.alpha_composite(im, (x, nb.height - im.height - 6)); x += 150
    x += 40
sheet.paste(nb.convert("RGB"), (12, yn + 30))
y1 = yn + 330
d.text((16, y1), "Moonstone fountain loop (10 frames)  ·  seamless tiles: fairy moss, petal path, moonstone paving (3x3 repeats)", font=small, fill=(220, 220, 230))
x = 16
fr = sorted(glob.glob(f"{A}/fountains/moonstone_fountain/frames_1x/f*.png"))
for p in fr:
    im = Image.open(p).convert("RGBA"); tile = Image.new("RGBA", im.size, (40, 70, 40, 255)); tile.alpha_composite(im)
    tile = tile.resize((int(im.width * 0.5), int(im.height * 0.5))); sheet.paste(tile.convert("RGB"), (x, y1 + 30)); x += tile.width + 4
for n in ("fairy_moss_v1", "petal_path_v1", "moonstone_paving_v1"):
    p = f"{F}/previews/tile_{n}_3x3.png"
    if os.path.exists(p):
        im = Image.open(p).resize((340, 340)); sheet.paste(im, (x + 10, y1 + 30)); x += 352
sheet.save(F + "/previews/contact_sheet.png", optimize=True)
print("contact sheet", sheet.size)
