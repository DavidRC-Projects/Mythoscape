"""tools/make_contact_sheet.py - labelled grid of all concept images."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from monsters import registry  # noqa: E402

IMG_DIR = sys.argv[1] if len(sys.argv) > 1 else "images"
OUT = os.path.join(IMG_DIR, "contact_sheet.png")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TILE, LABEL, COLS, PAD = 340, 58, 5, 10


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


registry.load_all()
order = ["dragon_green", "dragon_red", "dragon_black", "goblin_grunt", "goblin_shaman",
         "skeleton_warrior", "skeleton_mage", "spider_giant", "spider_broodmother",
         "void_spawn", "void_brute", "giant_hill", "giant_ice", "wolf_grey", "wolf_dire",
         "bog_lurker", "stone_golem", "barrow_wraith", "cave_gnasher", "rot_ghoul"]
rows = (len(order) + COLS - 1) // COLS
title_h = 70
W = COLS * (TILE + PAD) + PAD
H = title_h + rows * (TILE + LABEL + PAD) + PAD
sheet = Image.new("RGB", (W, H), (38, 36, 33))
d = ImageDraw.Draw(sheet)
d.text((PAD + 4, 14), "Monster concepts - low-poly, flat-shaded, OSRS-style", fill=(226, 214, 180),
       font=font(FONT_B, 26))
d.text((PAD + 4, 46), "Rendered in Panda3D from the reference code in code/monsters/  "
       "(1 unit = 1 m, player = 1.8 m)", fill=(170, 162, 140), font=font(FONT, 15))
f_name, f_info = font(FONT_B, 18), font(FONT, 13)
for i, key in enumerate(order):
    mt = registry.MONSTERS[key]
    x = PAD + (i % COLS) * (TILE + PAD)
    y = title_h + (i // COLS) * (TILE + LABEL + PAD)
    im = Image.open(os.path.join(IMG_DIR, f"{key}.png")).convert("RGB").resize((TILE, TILE), Image.LANCZOS)
    sheet.paste(im, (x, y))
    d.rectangle([x, y + TILE, x + TILE - 1, y + TILE + LABEL - 1], fill=(56, 52, 46))
    d.text((x + 8, y + TILE + 6), mt.name, fill=(236, 226, 196), font=f_name)
    d.text((x + 8, y + TILE + 32),
           f"lvl {mt.stats.level} | {mt.stats.hp} HP | {mt.height_m:.1f} m | {key}.png",
           fill=(180, 172, 150), font=f_info)
sheet.save(OUT)
print("wrote", OUT, sheet.size)
