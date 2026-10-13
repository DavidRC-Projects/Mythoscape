"""dragon/frames/<anim>_<facing>_<i>.png -> dragon/<anim>_<facing>.png strips + dragon/meta.json + previews/dragon_frames_sheet.png"""
import os, json, numpy as np
from PIL import Image, ImageDraw, ImageFont
D = "/workspace/emberdeep_hd"
FR = f"{D}/dragon/frames"
ANIMS = {"idle": 4, "walk": 8, "breath": 8, "hit": 3, "death": 8}
FPS = {"idle": 6, "walk": 10, "breath": 1 / 0.15, "hit": 10, "death": 8}
FACINGS = ["s", "e", "n", "w"]
W, H = 768, 512
edge = np.ones((H, W), np.float32)
ramp = np.clip(np.arange(W) / 28, 0, 1); edge *= np.minimum(ramp, ramp[::-1])[None]
rampy = np.clip(np.arange(H) / 28, 0, 1); edge *= np.minimum(rampy, rampy[::-1])[:, None]
missing = []
for a, n in ANIMS.items():
    for f in FACINGS:
        strip = Image.new("RGBA", (W * n, H))
        for i in range(n):
            p = f"{FR}/{a}_{f}_{i}.png"
            if not os.path.exists(p):
                missing.append(p); continue
            im = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)
            im[..., 3] *= edge  # baked contact shadow never ends in a hard canvas edge
            strip.paste(Image.fromarray(im.astype(np.uint8), "RGBA"), (i * W, 0))
        strip.save(f"{D}/dragon/{a}_{f}.png", optimize=True)
meta = {
    "frame_w": W, "frame_h": H, "feet_px": [384, 330],
    "facings": FACINGS, "w_is_rendered": True,
    "anims": {a: {"frames": n, "fps": round(FPS[a], 3), "loop": a in ("idle", "walk")} for a, n in ANIMS.items()},
    "breath": {"release_frame": 4, "frame_secs": 0.15, "release_at_secs": 0.6,
               "note": "start on the EMBER_CONE telegraph tick; frame 4 (0.6 s = one server tick) is when the hit lands"},
    "file": "{anim}_{facing}.png (frames left to right)",
    "draw": "draw height = WYRM_TILES_H * tile_px for the full 512 px canvas; anchor feet_px on the wyrm's ground point",
}
json.dump(meta, open(f"{D}/dragon/meta.json", "w"), indent=1)
# contact sheet: every frame, 1/4 scale, rows = anim x facing
s = 4; cw, ch = W // s, H // s
rows = [(a, f) for a in ANIMS for f in FACINGS]
sheet = Image.new("RGBA", (110 + cw * 8, ch * len(rows)), (58, 54, 52, 255))
dr = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
except Exception:
    font = None
for r, (a, f) in enumerate(rows):
    st = Image.open(f"{D}/dragon/{a}_{f}.png")
    dr.text((8, r * ch + ch // 2 - 8), f"{a} {f}", fill=(255, 220, 170), font=font)
    for i in range(ANIMS[a]):
        fr = st.crop((i * W, 0, i * W + W, H)).resize((cw, ch), Image.LANCZOS)
        sheet.alpha_composite(fr, (110 + i * cw, r * ch))
        if a == "breath" and i == 4:
            dr.rectangle((110 + i * cw, r * ch, 110 + i * cw + cw - 1, r * ch + ch - 1), outline=(255, 120, 40), width=2)
os.makedirs(f"{D}/previews", exist_ok=True)
sheet.convert("RGB").save(f"{D}/previews/dragon_frames_sheet.png", optimize=True)
print("assembled; missing", len(missing))
