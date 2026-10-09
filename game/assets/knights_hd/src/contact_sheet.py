"""Previews: grey lineup (1x/2x at game scale, bosses scaled) + contact sheet (heroes, facings, walk/attack strips)."""
import os
from PIL import Image, ImageDraw, ImageFont
A = "/workspace/knights_hd/assets"; P = "/workspace/knights_hd/previews"; os.makedirs(P, exist_ok=True)
KEYS = ["knight", "shadow_knight", "knight_captain_vorn", "barrow_knight", "sir_aldric", "magma_knight"]
LBL = {"knight": "Castle Knight (48)", "shadow_knight": "Shadow Knight (88)", "knight_captain_vorn": "Knight-Captain Vorn (92) boss x1.2",
       "barrow_knight": "Barrow Knight (44)", "sir_aldric": "Sir Aldric the Unquiet (52) boss x1.3", "magma_knight": "Magma Knight (78)"}
SC = {"knight_captain_vorn": 1.2, "sir_aldric": 1.3}
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
GREY = (128, 128, 128)


def spr(k, tag, st, fc, i):
    return Image.open(f"{A}/{k}/sprite_{tag}/{st}/{fc}/f{i:02d}.png").convert("RGBA")


def lineup():
    # 2x row (80 px tile) and 1x row (40 px tile) on mid grey with tile grid, feet on one baseline, bosses at their content scale
    W = 1400; H = 760
    im = Image.new("RGBA", (W, H), GREY + (255,)); d = ImageDraw.Draw(im)
    d.text((16, 12), "Mythoscape HD knights - grey lineup at game scale (south idle f00). Row 1: 2x (80 px tile). Row 2: 1x (40 px tile).", font=f, fill=(20, 20, 20))
    for row, (tag, tile, base_y) in enumerate((("2x", 80, 440), ("1x", 40, 700))):
        for x in range(0, W, tile):
            d.line([(x, base_y - tile * 4), (x, base_y + 10)], fill=(118, 118, 118))
        d.line([(0, base_y), (W, base_y)], fill=(100, 100, 100))
        for i, k in enumerate(KEYS):
            s = spr(k, tag, "idle", "s", 0); sc = SC.get(k, 1.0)
            if sc != 1.0:
                s = s.resize((int(s.width * sc), int(s.height * sc)), Image.LANCZOS)
            fx = 64 if tag == "1x" else 128; fy = 132 if tag == "1x" else 264
            cx = 120 + i * 225
            im.alpha_composite(s, (int(cx - fx * sc), int(base_y - fy * sc)))
            if row == 0:
                d.text((cx - 95, base_y + 14), LBL[k].split(" boss")[0].replace("Knight-Captain ", "Capt. ").replace(" the Unquiet", ""), font=f, fill=(15, 15, 15))
    im.convert("RGB").save(f"{P}/knights_hd_lineup_grey.png")


def contact():
    CW = 300; W = 6 * (CW + 12) + 12
    rows_h = 70 + CW + 40 + 300 + 30 + 6 * 160 + 20
    sheet = Image.new("RGB", (W, rows_h), (16, 18, 22)); d = ImageDraw.Draw(sheet)
    d.text((16, 18), "Mythoscape - HD attackable knights (hero / facings / walk + attack)", font=F, fill=(255, 220, 150))
    y = 64
    for i, k in enumerate(KEYS):
        p = f"{A}/{k}/{k}_hero_2048_bg.jpg"
        if os.path.exists(p):
            sheet.paste(Image.open(p).resize((CW, CW), Image.LANCZOS), (12 + i * (CW + 12), y))
        d.text((12 + i * (CW + 12), y + CW + 6), LBL[k], font=f, fill=(230, 210, 200))
    y += CW + 34
    d.text((16, y), "Idle at 2x - facings s / e / n / w (grey = game-ish ground)", font=f, fill=(200, 200, 200)); y += 22
    for i, k in enumerate(KEYS):
        x0 = 12 + i * (CW + 12)
        tile = Image.new("RGBA", (CW, 270), GREY + (255,))
        for j, fc in enumerate("senw"):
            s = spr(k, "2x", "idle", fc, 0).crop((40, 20, 216, 288)).resize((75, 114), Image.LANCZOS)
            tile.alpha_composite(s, (j * 75, 140))
            s2 = spr(k, "2x", "idle", fc, 0).crop((40, 20, 216, 288)).resize((75, 114), Image.LANCZOS) if False else None
        big = spr(k, "2x", "idle", "s", 0).crop((48, 40, 208, 288)).resize((100, 155), Image.LANCZOS)
        tile.alpha_composite(big, (100, -10))
        sheet.paste(tile.convert("RGB"), (x0, y))
    y += 280
    d.text((16, y), "Per knight (2x, facing e): walk f00-f07 | attack f00-f05 (impact f03) | hit f00-f02 | death f00-f05", font=f, fill=(200, 200, 200)); y += 22
    for k in KEYS:
        strip = Image.new("RGBA", (W - 24, 150), GREY + (255,))
        x = 0
        for st, n in (("walk", 8), ("attack", 6), ("hit", 3), ("death", 6)):
            for i in range(n):
                s = spr(k, "2x", st, "e", i).crop((0, 40, 256, 288)).resize((76, 74 * 125 // 74), Image.LANCZOS)
                strip.alpha_composite(s, (x, 20)); x += 76
            x += 10
        ImageDraw.Draw(strip).text((4, 2), LBL[k], font=f, fill=(15, 15, 15))
        sheet.paste(strip.convert("RGB"), (12, y)); y += 160
    sheet.save(f"{P}/knights_hd_contact_sheet.png")


if __name__ == "__main__":
    lineup(); contact(); print("ok")
