"""tools/make_contact_sheets.py - one labelled contact sheet per group (town, castle, pets,
dungeons). Per prop: Blender concept (game camera) | Panda3D game camera | Panda3D 3/4 |
the real in-game 1x sprite at TRUE pixel size on a 40 px tile grid (plus the old sprite's
width as a red bracket when known), with title, key, triangles and the review score.

    /workspace/monsters_venv/bin/python tools/make_contact_sheets.py
Scores + notes come from review/scores.json (edit it after each review pass).
"""
import glob
import json
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GROUP_TITLES = {"town": "Town & services (bank, smithy, well, fountain, shops)",
                "castle": "Castle keep", "pets": "Pet Emporium cages", "dungeons": "Dungeon interiors (7 themes)"}


def font(p, s):
    try:
        return ImageFont.truetype(p, s)
    except OSError:
        return ImageFont.load_default()


def sprite_panel(key, meta, T):
    """In-game 1x sprite on a 40 px tile checker, magnified x2 (nearest) so pixels stay honest."""
    p = Image.new("RGB", (T, T), (60, 56, 50))
    d = ImageDraw.Draw(p)
    spath = os.path.join(ROOT, "sprites", "game", key + "_1x.png")
    if not os.path.exists(spath):
        return p
    spr = Image.open(spath).convert("RGBA")
    info = json.load(open(os.path.join(ROOT, "sprites", "game", key + ".json")))["images"][key + "_1x.png"]
    Z = 2
    tile = 40 * Z
    for ty in range(0, T, tile // 2):          # ground tiles, squashed like the game's floor rows
        for tx in range(0, T, tile):
            c = (74, 68, 60) if ((tx // tile) + (ty // (tile // 2))) % 2 else (68, 62, 55)
            d.rectangle([tx, ty, tx + tile - 1, ty + tile // 2 - 1], fill=c)
    big = spr.resize((spr.width * Z, spr.height * Z), Image.NEAREST)
    ox, oy = info["origin_px"]
    ax, ay = T // 2, int(T * 0.72)
    x0, y0 = int(ax - ox * Z), int(ay - oy * Z)
    if big.width > T or big.height > T:            # huge props (giant throne): scale to fit
        s = min((T - 8) / big.width, (T - 8) / big.height)
        big = big.resize((int(big.width * s), int(big.height * s)), Image.NEAREST)
        x0, y0 = int(ax - ox * Z * s), int(ay - oy * Z * s)
    p.paste(big, (x0, y0), big)
    d.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], outline=(255, 240, 120))
    cur = (meta.get("game") or {}).get("current_px_at_tile40")
    f = font(FONT, 12)
    if cur:
        w = cur[0] * Z
        d.line([ax - w // 2, T - 16, ax + w // 2, T - 16], fill=(220, 70, 60), width=2)
        d.text((4, T - 14), f"old {cur[0]}x{cur[1]}px", font=f, fill=(230, 120, 110))
    d.text((4, 3), f"in-game 1x {spr.width}x{spr.height}px (x2)", font=f, fill=(235, 230, 215))
    return p


def main():
    scores = {}
    sp = os.path.join(ROOT, "review", "scores.json")
    if os.path.exists(sp):
        scores = json.load(open(sp))
    metas = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, "json", "*.json")))]
    T, LBL, COLS = 250, 44, 2
    fb, fs, ft = font(FONTB, 17), font(FONT, 13), font(FONTB, 26)
    for group in ("town", "castle", "pets", "dungeons"):
        ms = [m for m in metas if m.get("group") == group]
        order = (scores.get("_order") or {}).get(group)
        if order:
            ms.sort(key=lambda m: order.index(m["key"]) if m["key"] in order else 99)
        rows = (len(ms) + COLS - 1) // COLS
        cellw = 4 * T + 3 * 6
        W = COLS * (cellw + 30) + 20
        H = 96 + rows * (T + LBL + 22)
        sheet = Image.new("RGB", (W, H), (36, 34, 31))
        d = ImageDraw.Draw(sheet)
        avg = [scores.get(m["key"], {}).get("score") for m in ms]
        avg = [a for a in avg if a is not None]
        d.text((20, 14), f"Mythoscape props - {GROUP_TITLES[group]}  ({len(ms)} props"
               + (f", mean score {sum(avg) / len(avg):.1f}/10" if avg else "") + ")", font=ft, fill=(240, 232, 210))
        d.text((20, 52), "per prop:  Blender concept (game camera: ortho, az 0, el 32)  |  Panda3D prop_loader, "
               "game camera  |  Panda3D 3/4 view  |  real 1x game sprite on 40 px tiles (red = old 2D sprite width)",
               font=fs, fill=(200, 192, 175))
        for i, m in enumerate(ms):
            key = m["key"]
            cx = 20 + (i % COLS) * (cellw + 30)
            cy = 96 + (i // COLS) * (T + LBL + 22)
            sc = scores.get(key, {})
            s = sc.get("score")
            col = (120, 210, 120) if (s or 0) >= 8 else (230, 120, 100)
            d.text((cx, cy), f"{m['title']}  [{key}]", font=fb, fill=(245, 238, 220))
            d.text((cx + cellw - 90, cy), f"{s}/10" if s is not None else "--/10", font=fb, fill=col)
            ids = ", ".join((m.get("game") or {}).get("ids") or []) or (m.get("game") or {}).get("theme", "")
            d.text((cx, cy + 22), f"{m['triangles']} tris  |  {ids}"[:120], font=fs, fill=(190, 182, 165))
            panels = [os.path.join(ROOT, "images", key + "_concept.png"),
                      os.path.join(ROOT, "panda_renders", key + "_panda.png"),
                      os.path.join(ROOT, "panda_renders", key + "_panda34.png")]
            for j, pth in enumerate(panels):
                x = cx + j * (T + 6)
                if os.path.exists(pth):
                    sheet.paste(Image.open(pth).convert("RGB").resize((T, T), Image.LANCZOS), (x, cy + LBL))
            sheet.paste(sprite_panel(key, m, T), (cx + 3 * (T + 6), cy + LBL))
        out = os.path.join(ROOT, "review", f"contact_{group}.png")
        sheet.save(out)
        print("wrote", out)


if __name__ == "__main__":
    main()
