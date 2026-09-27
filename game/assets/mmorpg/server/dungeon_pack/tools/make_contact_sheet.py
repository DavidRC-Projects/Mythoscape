"""tools/make_contact_sheet.py - labelled contact sheet: Blender concept (left) and the
Panda3D in-engine render (right) for every entrance, with triangle count and review score.

    /workspace/monsters_venv/bin/python tools/make_contact_sheet.py
Scores come from review/scores.json (edit it after each review pass).
"""
import glob
import json
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ORDER = ["dragon_lair", "goblin_cave", "skeleton_crypt", "spider_nest", "void_rift",
         "giants_cavern", "wolf_den"]


def font(p, s):
    try:
        return ImageFont.truetype(p, s)
    except OSError:
        return ImageFont.load_default()


def main():
    scores = {}
    sp = os.path.join(ROOT, "review", "scores.json")
    if os.path.exists(sp):
        scores = json.load(open(sp))
    keys = [k for k in ORDER if os.path.exists(os.path.join(ROOT, "json", k + ".json"))]
    keys += sorted(set(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "json", "*.json"))) - set(keys))
    T, LBL, COLS = 420, 58, 2          # 2 entrances per row, each = concept + panda
    rows = (len(keys) + COLS - 1) // COLS
    W = COLS * (2 * T + 20) + 20
    H = 70 + rows * (T + LBL + 20)
    sheet = Image.new("RGB", (W, H), (38, 36, 33))
    d = ImageDraw.Draw(sheet)
    d.text((20, 18), "Dungeon entrances - Blender concept (left) | Panda3D in-engine render (right)",
           font=font(FONTB, 24), fill=(235, 228, 210))
    for i, k in enumerate(keys):
        meta = json.load(open(os.path.join(ROOT, "json", k + ".json")))
        x = 20 + (i % COLS) * (2 * T + 20)
        y = 70 + (i // COLS) * (T + LBL + 20)
        for j, path in enumerate((os.path.join(ROOT, "images", k + "_concept.png"),
                                  os.path.join(ROOT, "panda_renders", k + "_panda.png"))):
            if os.path.exists(path):
                sheet.paste(Image.open(path).convert("RGB").resize((T, T), Image.LANCZOS), (x + j * T, y))
        sc = scores.get(k, {})
        title = f"{meta.get('title', k)}"
        sub = f"{meta['triangles']} tris   opening {meta['openings'][0]['width']:.1f} x {meta['openings'][0]['height']:.1f} m"
        if sc:
            sub += f"   OSRS score {sc['score']}/10"
        d.text((x + 6, y + T + 6), title, font=font(FONTB, 22), fill=(240, 232, 214))
        d.text((x + 6, y + T + 32), sub, font=font(FONT, 17), fill=(200, 194, 178))
    out = os.path.join(ROOT, "images", "contact_sheet.png")
    sheet.save(out)
    print("wrote", out, sheet.size)
    sprite_preview(keys)


def sprite_preview(keys, view="front34", size=256):
    """2D route preview: the transparent sprites over a checkerboard + a grass tile."""
    tiles = []
    for k in keys:
        p = os.path.join(ROOT, "sprites", view, f"{k}_{size}.png")
        if os.path.exists(p):
            tiles.append((k, Image.open(p).convert("RGBA")))
    if not tiles:
        return
    th = max(t.height for _, t in tiles) + 40
    W = 20 + len(tiles) * (size + 16)
    img = Image.new("RGBA", (W, th + 60), (38, 36, 33, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 12), f"2D sprites ({view}, {size}px wide, transparent) - checker = alpha",
           font=font(FONTB, 18), fill=(235, 228, 210))
    for i, (k, t) in enumerate(tiles):
        x, y = 20 + i * (size + 16), 44
        chk = Image.new("RGBA", (size, t.height), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chk)
        for yy in range(0, t.height, 16):
            for xx in range(0, size, 16):
                cd.rectangle((xx, yy, xx + 15, yy + 15),
                             fill=(120, 120, 120, 255) if (xx + yy) // 16 % 2 else (160, 160, 160, 255))
        chk.alpha_composite(t)
        img.alpha_composite(chk, (x, y))
        d.text((x, y + t.height + 6), k, font=font(FONT, 15), fill=(220, 214, 198))
    out = os.path.join(ROOT, "images", "sprites_preview.png")
    img.convert("RGB").save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
