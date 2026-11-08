#!/usr/bin/env python3
"""Build a playable monsters_hd pack from a few painted stills.

Expects stills (jpg/png) named like:
  <id>_idle_s.<ext>  (required)
  <id>_idle_e.<ext>  (optional — mirrored for w if missing)
  <id>_idle_n.<ext>  (optional — falls back to idle_s)
  <id>_attack_e.<ext> / <id>_attack_s.<ext> (optional)

Writes sprite_1x + sprite_2x frame trees + meta.json + portrait.
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageChops, ImageEnhance, ImageOps

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
HD = os.path.join(ROOT, "monsters_hd")
ASSETS_GEN = os.path.expanduser(
    "~/.cursor/projects/Users-davidcarr-Mythoscape/assets"
)

CANVAS_2X = (256, 288)
FEET_2X = (128, 264)
STATES = {
    "idle": 4,
    "walk": 8,
    "attack": 6,
    "hit": 3,
    "death": 6,
}
FACINGS = ("s", "e", "n", "w")


def _find_still(mid: str, kind: str):
    for ext in ("png", "jpg", "jpeg", "webp"):
        for base in (ASSETS_GEN, os.path.join(HD, "_stills"), "."):
            path = os.path.join(base, f"{mid}_{kind}.{ext}")
            if os.path.isfile(path):
                return path
    return None


_REMBG_SESSION = None


def _rembg_session():
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session
        _REMBG_SESSION = new_session("u2netp")
    return _REMBG_SESSION


def _cutout(img: Image.Image) -> Image.Image:
    """Remove background via rembg (u2netp), else edge flood."""
    rgba = img.convert("RGBA")
    try:
        from rembg import remove
        from io import BytesIO
        out = remove(rgba, session=_rembg_session())
        if isinstance(out, Image.Image):
            return out.convert("RGBA")
        return Image.open(BytesIO(out)).convert("RGBA")
    except Exception as e:
        print(f"[cutout] rembg fallback ({e})")
    # Fallback: flood-fill near-corner colours to transparent.
    px = rgba.load()
    w, h = rgba.size
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    cr = sum(c[0] for c in corners) // 4
    cg = sum(c[1] for c in corners) // 4
    cb = sum(c[2] for c in corners) // 4
    tol = 42
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - cr) + abs(g - cg) + abs(b - cb) <= tol * 3:
                px[x, y] = (r, g, b, 0)
    return rgba


def _fit(img: Image.Image, canvas=CANVAS_2X, feet=FEET_2X) -> Image.Image:
    """Scale subject into canvas with feet near feet_px."""
    img = img.convert("RGBA")
    bb = img.getbbox()
    if not bb:
        return Image.new("RGBA", canvas, (0, 0, 0, 0))
    sub = img.crop(bb)
    cw, ch = canvas
    # Leave room for shadow / head — target ~78% of canvas height.
    max_h = int(ch * 0.78)
    max_w = int(cw * 0.88)
    scale = min(max_w / sub.width, max_h / sub.height)
    nw = max(1, int(sub.width * scale))
    nh = max(1, int(sub.height * scale))
    sub = sub.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    # Align bottom of subject a few px above feet y so baked shadow sits on feet.
    x = feet[0] - nw // 2
    y = feet[1] - nh + 4
    out.alpha_composite(sub, (x, y))
    return out


def _shift(img: Image.Image, dx=0, dy=0) -> Image.Image:
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(img, (dx, dy))
    return out


def _tint_red(img: Image.Image, amount=0.25) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (255, 60, 60, int(255 * amount)))
    base = img.copy()
    # Only tint opaque pixels.
    r, g, b, a = base.split()
    tinted = ImageChops.blend(base, Image.merge("RGBA", (*overlay.split()[:3], a)), amount)
    return Image.merge("RGBA", (*tinted.split()[:3], a))


def _load_facing(mid: str, facing: str, attack=False) -> Image.Image:
    kind = f"{'attack' if attack else 'idle'}_{facing}"
    path = _find_still(mid, kind)
    if path:
        return _fit(_cutout(Image.open(path)))
    if facing == "w":
        e = _load_facing(mid, "e", attack=attack)
        return ImageOps.mirror(e)
    if facing == "n":
        return _load_facing(mid, "s", attack=False)
    if attack:
        return _load_facing(mid, facing, attack=False)
    # Last resort: idle_s
    path = _find_still(mid, "idle_s")
    if not path:
        raise SystemExit(f"missing required still {mid}_idle_s")
    return _fit(_cutout(Image.open(path)))


def _frame_for(state: str, i: int, idle, attack, facing: str) -> Image.Image:
    if state == "idle":
        bob = (0, -1, 0, 1)[i % 4]
        return _shift(idle, 0, bob)
    if state == "walk":
        # Small bounce + lateral sway.
        phase = i % 8
        dx = (-2, -1, 0, 1, 2, 1, 0, -1)[phase]
        dy = (0, -2, -1, -2, 0, -2, -1, -2)[phase]
        return _shift(idle, dx, dy)
    if state == "attack":
        # Blend idle → attack → idle across 6 frames.
        if i <= 1:
            return _shift(idle, 0, -i)
        if i <= 3:
            return _shift(attack, (i - 2) * 2, 0)
        return _shift(idle if i == 5 else attack, 0, 0)
    if state == "hit":
        return _tint_red(_shift(idle, (-3, -5, -2)[i], (0, -2, 0)[i]))
    if state == "death":
        # Tip sideways / collapse downward.
        fallen = idle.rotate(-min(70, i * 14), resample=Image.Resampling.BICUBIC, expand=False)
        return _shift(fallen, i * 4, i * 6)
    return idle


def build(mid: str, name: str, look: str, level: int = 1, rgb=None):
    dst = os.path.join(HD, mid)
    os.makedirs(dst, exist_ok=True)

    idle = {f: _load_facing(mid, f, attack=False) for f in FACINGS}
    attack = {f: _load_facing(mid, f, attack=True) for f in FACINGS}
    if rgb:
        for f in FACINGS:
            idle[f] = _mul(idle[f], rgb)
            attack[f] = _mul(attack[f], rgb)

    for tag, canvas, feet in (
        ("2x", CANVAS_2X, FEET_2X),
        ("1x", (128, 144), (64, 132)),
    ):
        for state, nframes in STATES.items():
            for facing in FACINGS:
                folder = os.path.join(dst, f"sprite_{tag}", state, facing)
                os.makedirs(folder, exist_ok=True)
                base_idle = idle[facing]
                base_atk = attack[facing]
                if tag == "1x":
                    base_idle = base_idle.resize(canvas, Image.Resampling.LANCZOS)
                    base_atk = base_atk.resize(canvas, Image.Resampling.LANCZOS)
                for i in range(nframes):
                    fr = _frame_for(state, i, base_idle, base_atk, facing)
                    if fr.size != canvas:
                        fr = fr.resize(canvas, Image.Resampling.LANCZOS)
                    fr.save(os.path.join(folder, f"f{i:02d}.png"), optimize=True)

    # Portrait from idle south.
    port = idle["s"].copy()
    bb = port.getbbox() or (0, 0, *port.size)
    # Prefer upper body.
    head = port.crop((bb[0], bb[1], bb[2], min(bb[3], bb[1] + int((bb[3] - bb[1]) * 0.7))))
    head = ImageOps.contain(head, (512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    canvas.alpha_composite(head, ((512 - head.width) // 2, (512 - head.height) // 2))
    canvas.save(os.path.join(dst, "portrait_bust_512.png"), optimize=True)

    # Meta — reuse giant_rat skeleton with trimmed anchors (feet-based draw works without them).
    meta = {
        "id": mid,
        "name": name,
        "level": level,
        "sex": "-",
        "region": "Endless Depths",
        "boss": False,
        "look": look,
        "content_scale": 1.0,
        "scale_note": "painted stills pack — canvas matches batch-1 feet anchors",
        "canvas": {"1x": [128, 144], "2x": [256, 288], "4x": [512, 576]},
        "feet_px": {"1x": [64, 132], "2x": [128, 264], "4x": [256, 528]},
        "facings": {
            "s": "front / toward camera",
            "e": "screen right (game facing 1)",
            "n": "back / away",
            "w": "screen left (game facing -1)",
        },
        "game_facing_map": {"front": "s", "back": "n", "1": "e", "-1": "w"},
        "combat": {
            "attack_range": 1,
            "side_by_side": False,
            "attack_cooldown": None,
            "aggro_range": 0,
            "scale": 1.0,
        },
        "states": {
            "idle": {"frames": 4, "loop": True},
            "walk": {"frames": 8, "loop": True},
            "attack": {
                "frames": 6,
                "loop": False,
                "frame_starts": [0.0, 0.14, 0.3, 0.42, 0.6, 0.8],
                "impact_frame": 3,
                "impact_progress": 0.48,
            },
            "hit": {"frames": 3, "loop": False, "duration_s": 0.36},
            "death": {"frames": 6, "loop": False, "duration_s": 0.9, "hold_fade_s": 0.6},
        },
        "files": "sprite_{1x,2x}/{idle,walk,attack,hit,death}/{s,e,n,w}/fNN.png",
        "shadow": "soft contact shadow from source stills",
        "portrait": "portrait_bust_512.png",
        "anchors_4x": {},
        "head_top_idle_4x": 360.0,
        "healthbar_y_offset_1x": -48.0,
        "impact_reach_tiles": 0.9,
        "complete": True,
        "source": "painted_stills",
    }
    if rgb:
        meta["colour_multiply"] = list(rgb)
    with open(os.path.join(dst, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
        f.write("\n")
    print(f"built {mid} -> {dst}")


def _mul(img: Image.Image, rgb) -> Image.Image:
    r, g, b = rgb
    out = img.convert("RGBA")
    tint = Image.new("RGBA", out.size, (r, g, b, 255))
    mixed = ImageChops.multiply(out, tint)
    rr, gg, bb, _aa = mixed.split()
    _or, _og, _ob, oa = out.split()
    return Image.merge("RGBA", (rr, gg, bb, oa))


def main():
    specs = [
        ("goblin", "Goblin", "green-skinned goblin warrior, ragged leather, crude iron blade", 4, None),
        ("spider", "Giant Spider", "large hairy cave spider, dark brown, red eyes, fangs", 8, None),
        ("spiderling", "Spiderling", "small cave spider hatchling, dark brown, red eyes", 1, (220, 220, 220)),
        ("sewer_spider", "Sewer Spider", "filthy green-black sewer spider, wet carapace", 6, (150, 200, 160)),
        ("dragon", "Adamant Dragon", "teal adamant-scaled dragon, horns, folded wings", 40, None),
        ("petal_thrall", "Corrupted Fairy", "corrupted fairy thrall, torn petal wings, void eyes", 12, None),
    ]
    # Variants that recolour petal_thrall after it exists.
    petal_variants = [
        ("petal_thrall_thorn", "Thorn Choir Fairy", "thorn-choir fairy, bramble wings, rose-blood glow", 14, (200, 255, 180)),
        ("petal_thrall_mirror", "Mirror Bloom Fairy", "mirror-bloom fairy, silver petal wings", 16, (200, 220, 255)),
        ("petal_thrall_night", "Night Root Fairy", "night-root fairy, violet-black petals", 18, (180, 150, 220)),
        ("petal_elite_mirror", "Mirror Bloom Warden", "taller mirror-bloom warden fairy", 22, (180, 210, 255)),
        ("petal_elite_night", "Night Root Elder", "night-root elder fairy, deep violet", 24, (160, 120, 210)),
        ("petaldeep_queen", "Queen of Petaldeep", "petaldeep queen, regal corrupted fairy", 50, (255, 190, 220)),
    ]
    want = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    for mid, name, look, level, rgb in specs:
        if want and mid not in want:
            continue
        # spiderling / sewer_spider reuse spider stills via copy of names
        if mid in ("spiderling", "sewer_spider"):
            # Temporarily alias stills: pack builder looks for <mid>_idle_s — symlink keys.
            for facing in ("s", "e", "n"):
                for kind in ("idle", "attack"):
                    src = _find_still("spider", f"{kind}_{facing}")
                    if not src:
                        continue
                    # Place alias into gen assets folder.
                    ext = os.path.splitext(src)[1]
                    dst_alias = os.path.join(ASSETS_GEN, f"{mid}_{kind}_{facing}{ext}")
                    if not os.path.isfile(dst_alias):
                        Image.open(src).save(dst_alias)
        build(mid, name, look, level=level, rgb=rgb)

    # Petal variants clone from petal_thrall pack once built.
    thrall_dir = os.path.join(HD, "petal_thrall")
    if os.path.isdir(thrall_dir) and (not want or any(v[0] in want for v in petal_variants)):
        from clone_monsters_hd import clone
        for mid, name, look, level, rgb in petal_variants:
            if want and mid not in want:
                continue
            clone("petal_thrall", mid, rgb=rgb, name=name, look=look, level=level)


if __name__ == "__main__":
    main()
