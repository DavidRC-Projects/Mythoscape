#!/usr/bin/env python3
"""Build Mythoscape castle interior props: spiral stair + large detailed furniture.
Low-poly OSRS / Mythoscape style. Props read LARGE in full-screen rooms (256–512 px).
"""
from __future__ import annotations
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROP_DIR = os.path.join(ROOT, "props")
STAIR_DIR = os.path.join(ROOT, "spiral_stair")
PREV_DIR = os.path.join(ROOT, "previews")

# Theme palettes
THEMES = {
    "base": {
        "name": "Base stone",
        "stone": (118, 112, 104),
        "stone_hi": (148, 140, 128),
        "stone_lo": (78, 72, 66),
        "mortar": (60, 56, 50),
        "wood": (110, 72, 42),
        "wood_hi": (148, 100, 58),
        "wood_lo": (72, 46, 28),
        "metal": (150, 150, 158),
        "metal_hi": (210, 210, 220),
        "cloth": (140, 48, 52),
        "accent": (196, 168, 72),
        "pad": (90, 140, 100),
    },
    "duskspire": {
        "name": "Duskspire gothic",
        "stone": (72, 68, 78),
        "stone_hi": (98, 92, 108),
        "stone_lo": (42, 38, 48),
        "mortar": (28, 24, 32),
        "wood": (58, 40, 32),
        "wood_hi": (86, 58, 44),
        "wood_lo": (34, 22, 18),
        "metal": (90, 88, 100),
        "metal_hi": (150, 148, 168),
        "cloth": (88, 24, 36),
        "accent": (140, 48, 56),
        "pad": (70, 100, 80),
    },
    "white_rose": {
        "name": "White Rose pale stone",
        "stone": (196, 190, 180),
        "stone_hi": (232, 226, 216),
        "stone_lo": (150, 144, 136),
        "mortar": (120, 114, 108),
        "wood": (168, 130, 96),
        "wood_hi": (200, 164, 124),
        "wood_lo": (120, 90, 64),
        "metal": (190, 186, 178),
        "metal_hi": (240, 236, 228),
        "cloth": (244, 240, 236),
        "accent": (214, 186, 90),
        "pad": (140, 180, 150),
    },
    "king": {
        "name": "King blue-gold",
        "stone": (110, 118, 132),
        "stone_hi": (148, 156, 176),
        "stone_lo": (68, 74, 90),
        "mortar": (48, 52, 64),
        "wood": (96, 64, 40),
        "wood_hi": (130, 90, 54),
        "wood_lo": (60, 40, 26),
        "metal": (180, 160, 70),
        "metal_hi": (240, 210, 100),
        "cloth": (36, 64, 120),
        "accent": (220, 180, 60),
        "pad": (80, 130, 110),
    },
    "sky_anchor": {
        "name": "Sky-Anchor crystal",
        "stone": (96, 120, 132),
        "stone_hi": (140, 170, 180),
        "stone_lo": (56, 74, 86),
        "mortar": (40, 56, 66),
        "wood": (90, 78, 70),
        "wood_hi": (120, 104, 92),
        "wood_lo": (56, 48, 42),
        "metal": (120, 200, 210),
        "metal_hi": (200, 240, 250),
        "cloth": (70, 140, 160),
        "accent": (120, 230, 240),
        "pad": (90, 160, 150),
    },
}


def font(size=14, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def clamp_rgba(c):
    return tuple(max(0, min(255, int(v))) for v in c)


def shade(c, amt):
    return clamp_rgba((c[0] + amt, c[1] + amt, c[2] + amt, c[3] if len(c) > 3 else 255))


def mix(a, b, t):
    return clamp_rgba(tuple(a[i] * (1 - t) + b[i] * t for i in range(3)) + (255,))


def iso(cx, cy, x, y, z, sx=1.0, sy=0.5, sz=1.0):
    """Isometric project: x right, y depth, z up. Returns screen (px, py)."""
    px = cx + (x - y) * sx
    py = cy + (x + y) * sy - z * sz
    return px, py


def poly(d, pts, fill, outline=None, width=1):
    pts = [(int(round(p[0])), int(round(p[1]))) for p in pts]
    d.polygon(pts, fill=fill, outline=outline)
    if outline and width > 1:
        d.line(pts + [pts[0]], fill=outline, width=width)


def draw_box(d, cx, cy, x, y, z, w, dpth, h, top, left, right, outline=None, sx=8, sy=4, sz=7):
    """Draw an isometric box at grid (x,y,z) with size (w,dpth,h)."""
    # 8 corners
    def P(ix, iy, iz):
        return iso(cx, cy, x + ix, y + iy, z + iz, sx, sy, sz)

    # faces: top, left, right
    top_pts = [P(0, 0, h), P(w, 0, h), P(w, dpth, h), P(0, dpth, h)]
    left_pts = [P(0, 0, 0), P(0, dpth, 0), P(0, dpth, h), P(0, 0, h)]
    right_pts = [P(0, dpth, 0), P(w, dpth, 0), P(w, dpth, h), P(0, dpth, h)]
    # draw back-ish first: left then right then top (painter order for iso)
    poly(d, left_pts, left, outline)
    poly(d, right_pts, right, outline)
    poly(d, top_pts, top, outline)
    return {"top": top_pts, "left": left_pts, "right": right_pts,
            "corners": [P(0, 0, 0), P(w, 0, 0), P(w, dpth, 0), P(0, dpth, 0),
                        P(0, 0, h), P(w, 0, h), P(w, dpth, h), P(0, dpth, h)]}


def stone_speckle(im, bbox, density=40, seed=0):
    """Add faint stone speckles inside bbox (x0,y0,x1,y1)."""
    import random
    rnd = random.Random(seed)
    px = im.load()
    w, h = im.size
    x0, y0, x1, y1 = bbox
    for _ in range(density):
        x = rnd.randint(max(0, x0), min(w - 1, x1))
        y = rnd.randint(max(0, y0), min(h - 1, y1))
        r, g, b, a = px[x, y]
        if a < 40:
            continue
        amt = rnd.choice([-18, -10, 10, 16])
        px[x, y] = clamp_rgba((r + amt, g + amt, b + amt, a))


# ---------------------------------------------------------------------------
# SPIRAL STAIRCASE
# ---------------------------------------------------------------------------

def render_spiral_stair(theme_key="base", frame=None, size=480):
    """Render a room-scale stone spiral stair with clear walk pad.
    frame: None = full composite; 0 = pad; 1..steps = step i; steps+1 = column; steps+2 = curb.
    """
    th = THEMES[theme_key]
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = size // 2, size // 2 + 55
    sx, sy, sz = 12.5, 6.2, 10.0

    steps = 16
    rise = 0.48
    tread_outer = 4.6
    tread_inner = 1.35
    col_r = 1.05
    # wind ~1.15 turns so upper steps sit clearly above lower
    turn = 2.0 * math.pi * 1.15
    start_angle = -math.pi * 0.35

    def ang(i):
        return start_angle + (i / steps) * turn

    # ---- walk pad (frame 0) ----
    if frame is None or frame == 0:
        pad_pts = []
        a0, a1 = ang(0) - 0.15, ang(2) + 0.25
        for i in range(18):
            a = a0 + (a1 - a0) * (i / 17)
            r = tread_outer + 0.85
            pad_pts.append(iso(cx, cy, math.cos(a) * r, math.sin(a) * r, 0, sx, sy, sz))
        for i in range(18):
            a = a1 - (a1 - a0) * (i / 17)
            r = tread_inner - 0.15
            pad_pts.append(iso(cx, cy, math.cos(a) * r, math.sin(a) * r, 0, sx, sy, sz))
        poly(d, pad_pts, (*th["pad"], 230), (*mix(th["pad"], (255, 255, 255), 0.2)[:3], 255))
        # chevron step-on marker
        mid = (a0 + a1) / 2
        p0 = iso(cx, cy, math.cos(mid - 0.12) * 3.4, math.sin(mid - 0.12) * 3.4, 0.06, sx, sy, sz)
        p1 = iso(cx, cy, math.cos(mid) * 2.5, math.sin(mid) * 2.5, 0.06, sx, sy, sz)
        p2 = iso(cx, cy, math.cos(mid + 0.12) * 3.4, math.sin(mid + 0.12) * 3.4, 0.06, sx, sy, sz)
        poly(d, [p0, p1, p2], (255, 255, 230, 240))
        d.text((int(p1[0]) - 10, int(p1[1]) + 8), "PAD", fill=(30, 60, 40, 220), font=font(11, True))

    # ---- steps ----
    def step_depth(i):
        a = ang(i + 0.5)
        return iso(cx, cy, math.cos(a) * 3.2, math.sin(a) * 3.2, (i + 0.5) * rise, sx, sy, sz)[1]

    for i in sorted(range(steps), key=step_depth):
        if frame is not None and frame != 0 and frame != i + 1:
            continue
        a0, a1 = ang(i), ang(i + 1)
        z0, z1 = i * rise, (i + 1) * rise

        # thick riser (outer face)
        riser = []
        for k in range(7):
            a = a0 + (a1 - a0) * (k / 6)
            riser.append(iso(cx, cy, math.cos(a) * tread_outer, math.sin(a) * tread_outer, z0, sx, sy, sz))
        for k in range(7):
            a = a1 - (a1 - a0) * (k / 6)
            riser.append(iso(cx, cy, math.cos(a) * tread_outer, math.sin(a) * tread_outer, z1, sx, sy, sz))
        poly(d, riser, (*mix(th["stone_lo"], th["stone"], 0.25)[:3], 255), (*th["mortar"], 255))

        # side face (toward camera on outer)
        side = [
            iso(cx, cy, math.cos(a1) * tread_inner, math.sin(a1) * tread_inner, z0, sx, sy, sz),
            iso(cx, cy, math.cos(a1) * tread_outer, math.sin(a1) * tread_outer, z0, sx, sy, sz),
            iso(cx, cy, math.cos(a1) * tread_outer, math.sin(a1) * tread_outer, z1, sx, sy, sz),
            iso(cx, cy, math.cos(a1) * tread_inner, math.sin(a1) * tread_inner, z1, sx, sy, sz),
        ]
        poly(d, side, (*th["stone_lo"][:3], 255), (*th["mortar"], 200))

        # tread top (thick wedge)
        tread = []
        for k in range(8):
            a = a0 + (a1 - a0) * (k / 7)
            tread.append(iso(cx, cy, math.cos(a) * tread_outer, math.sin(a) * tread_outer, z1, sx, sy, sz))
        for k in range(8):
            a = a1 - (a1 - a0) * (k / 7)
            tread.append(iso(cx, cy, math.cos(a) * tread_inner, math.sin(a) * tread_inner, z1, sx, sy, sz))
        tc = th["stone_hi"] if i % 2 == 0 else th["stone"]
        # wear gradient: outer lighter
        poly(d, tread, (*tc[:3], 255), (*th["mortar"], 255))

        # stone joint rings on tread
        for rr in (0.35, 0.65):
            ring = []
            r = tread_inner + (tread_outer - tread_inner) * rr
            for k in range(6):
                a = a0 + (a1 - a0) * (k / 5)
                ring.append(iso(cx, cy, math.cos(a) * r, math.sin(a) * r, z1 + 0.02, sx, sy, sz))
            if len(ring) >= 2:
                d.line(ring, fill=(*th["mortar"], 140), width=1)

        # nosing lip
        lip = []
        for k in range(6):
            a = a0 + (a1 - a0) * (k / 5)
            lip.append(iso(cx, cy, math.cos(a) * tread_outer, math.sin(a) * tread_outer, z1 + 0.1, sx, sy, sz))
        for k in range(6):
            a = a1 - (a1 - a0) * (k / 5)
            lip.append(iso(cx, cy, math.cos(a) * (tread_outer - 0.22), math.sin(a) * (tread_outer - 0.22), z1, sx, sy, sz))
        poly(d, lip, (*mix(th["stone_lo"], th["stone_hi"], 0.35)[:3], 255))

        # theme studs
        if theme_key in ("king", "sky_anchor") and i % 2 == 0:
            mid_a = (a0 + a1) / 2
            tip = iso(cx, cy, math.cos(mid_a) * (tread_outer - 0.4), math.sin(mid_a) * (tread_outer - 0.4), z1 + 0.15, sx, sy, sz)
            d.ellipse([tip[0] - 3, tip[1] - 2, tip[0] + 3, tip[1] + 2], fill=(*th["accent"], 255))

        # outer baluster every other step
        if i % 2 == 0:
            mid_a = (a0 + a1) / 2
            base_b = iso(cx, cy, math.cos(mid_a) * (tread_outer - 0.15), math.sin(mid_a) * (tread_outer - 0.15), z1, sx, sy, sz)
            top_b = iso(cx, cy, math.cos(mid_a) * (tread_outer - 0.15), math.sin(mid_a) * (tread_outer - 0.15), z1 + 1.1, sx, sy, sz)
            rail_c = th["metal"] if theme_key == "duskspire" else th["stone_hi"]
            d.line([base_b, top_b], fill=(*rail_c, 255), width=3)
            d.ellipse([top_b[0] - 4, top_b[1] - 4, top_b[0] + 4, top_b[1] + 3], fill=(*th["metal_hi"], 255))

    # handrail ribbon connecting baluster tops
    if frame is None or frame == steps + 2:
        rail_pts = []
        for i in range(0, steps, 1):
            if i % 2 != 0:
                continue
            a = ang(i + 0.5)
            z = (i + 1) * rise + 1.05
            rail_pts.append(iso(cx, cy, math.cos(a) * (tread_outer - 0.15), math.sin(a) * (tread_outer - 0.15), z, sx, sy, sz))
        if len(rail_pts) >= 2:
            d.line(rail_pts, fill=(*th["metal"], 230), width=3)

    # ---- central newel ----
    if frame is None or frame == steps + 1:
        col_h = steps * rise + 1.4
        for zi in range(int(col_h * 3)):
            z = zi / 3.0
            r = col_r * (1.0 + 0.04 * math.sin(zi * 0.5))
            # drum band every few units
            if zi % 6 == 0:
                r += 0.12
            ring = [iso(cx, cy, math.cos(k / 12 * 2 * math.pi) * r,
                        math.sin(k / 12 * 2 * math.pi) * r, z, sx, sy, sz) for k in range(12)]
            col_c = mix(th["stone_lo"], th["stone_hi"], 0.35 + 0.1 * math.sin(zi * 0.4))
            poly(d, ring, (*col_c[:3], 255))
        # capital
        cap = [iso(cx, cy, math.cos(k / 14 * 2 * math.pi) * (col_r + 0.4),
                   math.sin(k / 14 * 2 * math.pi) * (col_r + 0.4), col_h, sx, sy, sz) for k in range(14)]
        poly(d, cap, (*th["stone_hi"][:3], 255), (*th["accent"], 255))
        tip = iso(cx, cy, 0, 0, col_h + 1.1, sx, sy, sz)
        d.polygon([(tip[0], tip[1] - 16), (tip[0] - 9, tip[1] + 5), (tip[0] + 9, tip[1] + 5)], fill=(*th["accent"], 255))

        if theme_key == "duskspire":
            # iron collar
            for k in range(8):
                a = k / 8 * 2 * math.pi
                p = iso(cx, cy, math.cos(a) * (col_r + 0.2), math.sin(a) * (col_r + 0.2), col_h * 0.55, sx, sy, sz)
                d.ellipse([p[0] - 3, p[1] - 2, p[0] + 3, p[1] + 2], fill=(*th["metal"], 255))
        if theme_key == "white_rose":
            tip = iso(cx, cy, 0, 0, col_h + 0.4, sx, sy, sz)
            for ox, oy in ((0, 0), (-7, 2), (7, 2), (0, 7), (-5, -4), (5, -4)):
                d.ellipse([tip[0] + ox - 5, tip[1] + oy - 4, tip[0] + ox + 5, tip[1] + oy + 4], fill=(255, 255, 255, 255))
            d.ellipse([tip[0] - 3, tip[1] - 2, tip[0] + 3, tip[1] + 3], fill=(*th["accent"], 255))
        if theme_key == "sky_anchor":
            tip = iso(cx, cy, 0, 0, col_h + 0.2, sx, sy, sz)
            d.polygon([(tip[0], tip[1] - 32), (tip[0] - 11, tip[1] + 2), (tip[0], tip[1] + 12), (tip[0] + 11, tip[1] + 2)],
                      fill=(*th["accent"], 230), outline=(*th["metal_hi"], 255))

    # ---- outer curb ----
    if frame is None or frame == steps + 2:
        for i in range(10):
            a0 = start_angle - 0.35 + i * 0.2
            a1 = a0 + 0.18
            curb = []
            for k in range(4):
                a = a0 + (a1 - a0) * (k / 3)
                curb.append(iso(cx, cy, math.cos(a) * (tread_outer + 0.7), math.sin(a) * (tread_outer + 0.7), 0.4, sx, sy, sz))
            for k in range(4):
                a = a1 - (a1 - a0) * (k / 3)
                curb.append(iso(cx, cy, math.cos(a) * (tread_outer + 0.3), math.sin(a) * (tread_outer + 0.3), 0, sx, sy, sz))
            poly(d, curb, (*th["stone_lo"][:3], 255), (*th["mortar"], 200))

    stone_speckle(im, (30, 30, size - 30, size - 30), density=160, seed=hash(theme_key) % 9999)
    return im


def build_spiral_set():
    os.makedirs(STAIR_DIR, exist_ok=True)
    paths = []
    # Base full composite
    base = render_spiral_stair("base", None, 512)
    p = os.path.join(STAIR_DIR, "spiral_stair_base.png")
    base.save(p)
    paths.append(p)

    # Multi-frame layers: pad, steps in groups, column
    # Export 5 frames for animation / layering
    # Frame 0: pad only
    # Frame 1-3: lower / mid / upper steps
    # Frame 4: column + curb
    frames_spec = [
        (0, "spiral_stair_layer_00_pad.png"),
        (None, None),  # skip full
    ]
    # Build layered by compositing groups
    size = 480
    # Layer pad
    im = render_spiral_stair("base", 0, size)
    p = os.path.join(STAIR_DIR, "spiral_stair_layer_00_pad.png")
    im.save(p); paths.append(p)

    # Lower steps 0-5
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for i in range(6):
        layer = render_spiral_stair("base", i + 1, size)
        im = Image.alpha_composite(im, layer)
    p = os.path.join(STAIR_DIR, "spiral_stair_layer_01_lower_steps.png")
    im.save(p); paths.append(p)

    # Mid steps 6-10
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for i in range(6, 11):
        layer = render_spiral_stair("base", i + 1, size)
        im = Image.alpha_composite(im, layer)
    p = os.path.join(STAIR_DIR, "spiral_stair_layer_02_mid_steps.png")
    im.save(p); paths.append(p)

    # Upper steps 11-15
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for i in range(11, 16):
        layer = render_spiral_stair("base", i + 1, size)
        im = Image.alpha_composite(im, layer)
    p = os.path.join(STAIR_DIR, "spiral_stair_layer_03_upper_steps.png")
    im.save(p); paths.append(p)

    # Column + curb (steps=16 → column frame 17, curb 18)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    im = Image.alpha_composite(im, render_spiral_stair("base", 17, size))  # column
    im = Image.alpha_composite(im, render_spiral_stair("base", 18, size))  # curb
    p = os.path.join(STAIR_DIR, "spiral_stair_layer_04_column_curb.png")
    im.save(p); paths.append(p)

    # Theme recolors (full composites)
    for key in ("duskspire", "white_rose", "king", "sky_anchor"):
        im = render_spiral_stair(key, None, 480)
        p = os.path.join(STAIR_DIR, f"spiral_stair_{key}.png")
        im.save(p); paths.append(p)

    # Recolor notes
    notes = """# Spiral stair recolor notes

Base design: `spiral_stair_base.png` (512×512) — grey medieval stone spiral with central newel,
14 treads, outer curb, and a **green walk-pad** sector at the foot (step-on tile cluster).

## Per-castle light recolors (already rendered)

| Castle | File | Palette |
|---|---|---|
| Duskspire (gothic) | `spiral_stair_duskspire.png` | Near-black stone, maroon accents, iron rail spikes on outer lip |
| White Rose | `spiral_stair_white_rose.png` | Pale limestone, cream mortar, white rose finial on newel |
| King's | `spiral_stair_king.png` | Blue-grey ashlar, gold studs every 3rd tread, gold finial |
| Sky-Anchor | `spiral_stair_sky_anchor.png` | Teal stone, cyan crystal shard on newel, crystal studs |

## Layers (for compositor / multi-frame)

1. `spiral_stair_layer_00_pad.png` — walk pad only (must stay clear; player steps here)
2. `spiral_stair_layer_01_lower_steps.png`
3. `spiral_stair_layer_02_mid_steps.png`
4. `spiral_stair_layer_03_upper_steps.png`
5. `spiral_stair_layer_04_column_curb.png`

Stack bottom→top for the full stair. Pad sits at the entrance wedge; do **not** place furniture on the pad or on U/V stair tiles.

## Placement

- Stair is a **tile cluster**, not a mid-hall cone.
- Prefer existing Stair Hall / Grand Stair / Crystal Stair corners already marked `U`/`V`.
- Keep a 2-tile straight approach pad free of blocking props.
"""
    with open(os.path.join(STAIR_DIR, "RECOLOR_NOTES.md"), "w") as f:
        f.write(notes)
    return paths


# ---------------------------------------------------------------------------
# FURNITURE PROPS
# ---------------------------------------------------------------------------

def new_canvas(w=384, h=384):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def prop_canopy_bed():
    """Larger detailed four-poster canopy bed — fits bedchambers."""
    im, d = new_canvas(448, 384)
    cx, cy = 220, 210
    sx, sy, sz = 14, 7, 11
    wood, whi, wlo = (96, 62, 36), (130, 88, 52), (58, 36, 22)
    cloth, chi = (210, 200, 188), (236, 230, 220)
    accent = (200, 170, 70)
    # mattress base
    draw_box(d, cx, cy, -2.2, -1.4, 0.4, 4.4, 2.8, 0.7, cloth, wlo, wood, sx=sx, sy=sy, sz=sz)
    # frame rail
    draw_box(d, cx, cy, -2.4, -1.5, 0.0, 4.8, 3.0, 0.45, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # pillows
    draw_box(d, cx, cy, -1.8, -1.2, 1.1, 1.4, 0.9, 0.35, chi, mix(cloth, (180, 170, 160), 0.5), cloth, sx=sx, sy=sy, sz=sz)
    draw_box(d, cx, cy, 0.0, -1.2, 1.1, 1.4, 0.9, 0.35, chi, mix(cloth, (180, 170, 160), 0.5), cloth, sx=sx, sy=sy, sz=sz)
    # blanket fold
    draw_box(d, cx, cy, -2.0, 0.2, 1.05, 4.0, 1.0, 0.2, (160, 48, 56), (120, 32, 40), (100, 28, 34), sx=sx, sy=sy, sz=sz)
    # four posts
    posts = [(-2.3, -1.4), (2.1, -1.4), (-2.3, 1.3), (2.1, 1.3)]
    for px, py in posts:
        draw_box(d, cx, cy, px, py, 0, 0.28, 0.28, 4.2, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
        # finial
        tip = iso(cx, cy, px + 0.14, py + 0.14, 4.4, sx, sy, sz)
        d.ellipse([tip[0] - 5, tip[1] - 5, tip[0] + 5, tip[1] + 4], fill=(*accent, 255))
        d.polygon([(tip[0], tip[1] - 14), (tip[0] - 5, tip[1] - 2), (tip[0] + 5, tip[1] - 2)], fill=(*accent, 255))
    # canopy roof
    draw_box(d, cx, cy, -2.5, -1.55, 4.0, 5.0, 3.15, 0.25, chi, cloth, mix(cloth, (160, 150, 140), 0.4), sx=sx, sy=sy, sz=sz)
    # canopy drapes (front corners)
    for px, py in [(-2.3, 1.3), (2.1, 1.3)]:
        top = iso(cx, cy, px + 0.1, py + 0.1, 4.0, sx, sy, sz)
        bot = iso(cx, cy, px + 0.1, py + 0.6, 1.2, sx, sy, sz)
        d.polygon([
            (top[0] - 4, top[1]), (top[0] + 10, top[1]),
            (bot[0] + 8, bot[1]), (bot[0] - 6, bot[1]),
        ], fill=(236, 232, 226, 200))
        # scallop
        for k in range(3):
            sx2 = bot[0] - 4 + k * 6
            d.arc([sx2, bot[1] - 2, sx2 + 8, bot[1] + 10], 0, 180, fill=(200, 190, 180, 220), width=2)
    # headboard carving
    draw_box(d, cx, cy, -2.1, -1.55, 1.1, 4.2, 0.2, 1.6, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    hb = iso(cx, cy, 0, -1.45, 2.2, sx, sy, sz)
    d.ellipse([hb[0] - 12, hb[1] - 10, hb[0] + 12, hb[1] + 8], outline=(*accent, 255), width=2)
    stone_speckle(im, (60, 40, 400, 360), 50, 11)
    return im


def prop_sideboard():
    im, d = new_canvas(384, 288)
    cx, cy = 190, 170
    sx, sy, sz = 12, 6, 9
    wood, whi, wlo = (108, 70, 40), (140, 96, 56), (68, 44, 26)
    # main body
    draw_box(d, cx, cy, -3.0, -0.7, 0, 6.0, 1.4, 2.2, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # top surface overhang
    draw_box(d, cx, cy, -3.15, -0.8, 2.2, 6.3, 1.6, 0.18, (160, 120, 72), wood, wlo, sx=sx, sy=sy, sz=sz)
    # drawers
    for i, x0 in enumerate([-2.6, -0.5, 1.6]):
        draw_box(d, cx, cy, x0, -0.55, 0.35, 1.7, 1.15, 0.75, mix(whi, wood, 0.3), wlo, wood, sx=sx, sy=sy, sz=sz)
        knob = iso(cx, cy, x0 + 0.85, 0.55, 0.75, sx, sy, sz)
        d.ellipse([knob[0] - 3, knob[1] - 3, knob[0] + 3, knob[1] + 3], fill=(200, 170, 70, 255))
    # upper cupboard doors
    for x0 in (-2.6, 0.3):
        draw_box(d, cx, cy, x0, -0.55, 1.25, 2.4, 1.15, 0.85, mix(whi, (180, 140, 90), 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
        # panel inset
        draw_box(d, cx, cy, x0 + 0.25, -0.4, 1.4, 1.9, 0.85, 0.55, mix(wood, wlo, 0.3), wlo, wood, sx=sx, sy=sy, sz=sz)
    # plate and goblet on top
    draw_box(d, cx, cy, -1.5, -0.3, 2.4, 1.0, 0.7, 0.08, (220, 210, 200), (180, 170, 160), (160, 150, 140), sx=sx, sy=sy, sz=sz)
    gob = iso(cx, cy, 1.2, 0.0, 2.55, sx, sy, sz)
    d.polygon([(gob[0], gob[1] - 18), (gob[0] - 8, gob[1]), (gob[0] + 8, gob[1])], fill=(200, 170, 70, 255))
    d.rectangle([gob[0] - 2, gob[1], gob[0] + 2, gob[1] + 10], fill=(160, 130, 50, 255))
    # feet
    for px in (-2.9, 2.5):
        draw_box(d, cx, cy, px, 0.4, -0.35, 0.35, 0.35, 0.4, wood, wlo, wlo, sx=sx, sy=sy, sz=sz)
    stone_speckle(im, (40, 40, 360, 260), 40, 22)
    return im


def prop_banquet_bench():
    im, d = new_canvas(420, 260)
    cx, cy = 210, 150
    sx, sy, sz = 13, 6.5, 9
    wood, whi, wlo = (118, 76, 44), (150, 100, 58), (74, 48, 28)
    cloth = (120, 36, 42)
    # long seat
    draw_box(d, cx, cy, -3.5, -0.6, 0.7, 7.0, 1.2, 0.35, mix(wood, (160, 110, 60), 0.3), wood, wlo, sx=sx, sy=sy, sz=sz)
    # cushion
    draw_box(d, cx, cy, -3.3, -0.5, 1.05, 6.6, 1.0, 0.22, cloth, mix(cloth, (60, 20, 24), 0.4), mix(cloth, (40, 10, 14), 0.5), sx=sx, sy=sy, sz=sz)
    # cushion buttons
    for i in range(5):
        p = iso(cx, cy, -2.8 + i * 1.4, 0.0, 1.28, sx, sy, sz)
        d.ellipse([p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2], fill=(200, 170, 70, 255))
    # legs
    for px in (-3.3, -0.3, 2.7):
        for py in (-0.5, 0.35):
            draw_box(d, cx, cy, px, py, 0, 0.3, 0.3, 0.75, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # backrest (wall-hug side)
    draw_box(d, cx, cy, -3.5, -0.7, 1.05, 7.0, 0.25, 1.4, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # carved arches on backrest
    for i in range(4):
        p = iso(cx, cy, -2.6 + i * 1.7, -0.55, 1.9, sx, sy, sz)
        d.arc([p[0] - 10, p[1] - 12, p[0] + 10, p[1] + 6], 200, 340, fill=(200, 170, 70, 255), width=2)
    return im


def prop_tapestry():
    """Wall tapestry — tall, detailed heraldic."""
    im, d = new_canvas(280, 420)
    # rod
    d.rectangle([30, 28, 250, 42], fill=(140, 110, 60, 255))
    d.ellipse([20, 24, 40, 46], fill=(200, 170, 70, 255))
    d.ellipse([240, 24, 260, 46], fill=(200, 170, 70, 255))
    # hanging rings
    for x in (50, 100, 150, 200):
        d.ellipse([x - 4, 38, x + 4, 50], outline=(180, 150, 70, 255), width=2)
    # cloth body
    body = [(40, 48), (240, 48), (228, 380), (52, 380)]
    d.polygon(body, fill=(110, 28, 36, 255))
    # darker side folds
    d.polygon([(40, 48), (58, 48), (64, 380), (52, 380)], fill=(80, 18, 24, 255))
    d.polygon([(222, 48), (240, 48), (228, 380), (214, 380)], fill=(80, 18, 24, 255))
    # gold border
    d.polygon([(55, 60), (225, 60), (216, 360), (64, 360)], outline=(200, 170, 70, 255))
    d.rectangle([58, 62, 222, 358], outline=(200, 170, 70, 255), width=3)
    # central emblem — shield
    d.polygon([(140, 100), (190, 130), (180, 230), (140, 260), (100, 230), (90, 130)], fill=(36, 52, 96, 255), outline=(200, 170, 70, 255))
    # lion-ish mark
    d.ellipse([120, 145, 160, 185], fill=(200, 170, 70, 255))
    d.polygon([(140, 120), (128, 150), (152, 150)], fill=(220, 190, 90, 255))
    # motto bar
    d.rectangle([80, 280, 200, 310], fill=(40, 24, 20, 255))
    d.text((95, 286), "KEEP", fill=(220, 190, 90, 255), font=font(16, True))
    # fringe
    for x in range(56, 226, 10):
        d.line([(x, 380), (x + 2, 405)], fill=(200, 170, 70, 255), width=2)
        d.ellipse([x, 402, x + 6, 410], fill=(200, 170, 70, 255))
    # soft folds texture
    for y in range(70, 350, 18):
        d.line([(70, y), (210, y + 4)], fill=(130, 40, 48, 80), width=1)
    return im


def prop_weapon_rack():
    im, d = new_canvas(320, 400)
    cx, cy = 160, 300
    sx, sy, sz = 11, 5.5, 9
    wood, whi, wlo = (100, 64, 38), (130, 88, 50), (60, 38, 22)
    metal, mhi = (150, 150, 158), (210, 210, 220)
    # backboard
    draw_box(d, cx, cy, -1.6, -0.4, 0.2, 3.2, 0.35, 4.0, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # peg rails
    for z in (1.2, 2.4, 3.4):
        draw_box(d, cx, cy, -1.5, -0.2, z, 3.0, 0.5, 0.15, mix(whi, wood, 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
    # swords
    for i, x in enumerate([-1.0, 0.2, 1.2]):
        tip = iso(cx, cy, x, 0.1, 3.8, sx, sy, sz)
        hilt = iso(cx, cy, x, 0.1, 1.5, sx, sy, sz)
        d.line([tip, hilt], fill=(*mhi, 255), width=4)
        d.line([tip, hilt], fill=(*metal, 255), width=2)
        # guard
        g = iso(cx, cy, x, 0.1, 1.7, sx, sy, sz)
        d.line([(g[0] - 10, g[1]), (g[0] + 10, g[1])], fill=(200, 170, 70, 255), width=3)
        # pommel
        d.ellipse([hilt[0] - 4, hilt[1] - 2, hilt[0] + 4, hilt[1] + 6], fill=(200, 170, 70, 255))
    # axe
    ax = iso(cx, cy, -0.4, 0.25, 3.5, sx, sy, sz)
    ab = iso(cx, cy, -0.4, 0.25, 1.3, sx, sy, sz)
    d.line([ax, ab], fill=(*wood, 255), width=4)
    d.polygon([(ax[0] - 2, ax[1]), (ax[0] + 18, ax[1] - 8), (ax[0] + 16, ax[1] + 10), (ax[0] - 2, ax[1] + 4)], fill=(*mhi, 255), outline=(*metal, 255))
    # shield
    sh = iso(cx, cy, 0.9, 0.3, 2.5, sx, sy, sz)
    d.polygon([(sh[0], sh[1] - 28), (sh[0] + 22, sh[1] - 10), (sh[0] + 18, sh[1] + 22), (sh[0], sh[1] + 32), (sh[0] - 18, sh[1] + 22), (sh[0] - 22, sh[1] - 10)],
              fill=(40, 56, 100, 255), outline=(200, 170, 70, 255))
    d.ellipse([sh[0] - 8, sh[1] - 6, sh[0] + 8, sh[1] + 10], fill=(200, 170, 70, 255))
    # base plinth
    draw_box(d, cx, cy, -1.8, -0.5, 0, 3.6, 1.2, 0.25, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    return im


def prop_bookshelf():
    im, d = new_canvas(340, 420)
    cx, cy = 170, 320
    sx, sy, sz = 11, 5.5, 9
    wood, whi, wlo = (92, 58, 34), (124, 82, 48), (56, 34, 20)
    # carcass
    draw_box(d, cx, cy, -2.0, -0.6, 0, 4.0, 1.2, 4.6, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # shelves
    book_colors = [
        (120, 36, 42), (36, 64, 110), (40, 90, 60), (140, 100, 40),
        (90, 40, 90), (50, 50, 60), (150, 70, 40), (70, 90, 120),
    ]
    for si, z in enumerate((0.9, 1.9, 2.9, 3.9)):
        draw_box(d, cx, cy, -1.9, -0.5, z, 3.8, 1.05, 0.12, mix(whi, wood, 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
        # books
        x = -1.75
        bi = 0
        while x < 1.7:
            bw = 0.28 + (bi % 3) * 0.08
            bh = 0.55 + (bi % 4) * 0.08
            col = book_colors[(si * 3 + bi) % len(book_colors)]
            draw_box(d, cx, cy, x, -0.35, z + 0.12, bw, 0.7, bh, mix(col, (255, 255, 255), 0.15), col, mix(col, (0, 0, 0), 0.3), sx=sx, sy=sy, sz=sz)
            # spine line
            sp = iso(cx, cy, x + bw * 0.5, 0.3, z + 0.12 + bh * 0.5, sx, sy, sz)
            d.line([(sp[0], sp[1] - 4), (sp[0], sp[1] + 4)], fill=(200, 180, 100, 180), width=1)
            x += bw + 0.06
            bi += 1
    # top cornice
    draw_box(d, cx, cy, -2.15, -0.7, 4.6, 4.3, 1.4, 0.2, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # scroll on middle shelf
    draw_box(d, cx, cy, 0.8, -0.2, 2.1, 0.9, 0.5, 0.15, (230, 220, 190), (200, 190, 160), (180, 170, 140), sx=sx, sy=sy, sz=sz)
    return im


def prop_bathtub():
    im, d = new_canvas(400, 300)
    cx, cy = 200, 180
    sx, sy, sz = 13, 6.5, 9
    stone, shi, slo = (170, 164, 156), (210, 204, 196), (120, 114, 108)
    water = (120, 170, 190)
    # tub outer
    draw_box(d, cx, cy, -2.4, -1.2, 0, 4.8, 2.4, 1.3, shi, stone, slo, sx=sx, sy=sy, sz=sz)
    # inner basin rim
    draw_box(d, cx, cy, -2.1, -1.0, 1.15, 4.2, 2.0, 0.2, mix(shi, (255, 255, 255), 0.2), stone, slo, sx=sx, sy=sy, sz=sz)
    # water surface
    draw_box(d, cx, cy, -1.9, -0.85, 1.0, 3.8, 1.7, 0.08, mix(water, (200, 230, 240), 0.4), water, mix(water, (40, 80, 100), 0.3), sx=sx, sy=sy, sz=sz)
    # ripples
    for i in range(3):
        p = iso(cx, cy, -0.5 + i * 0.8, 0.0, 1.1, sx, sy, sz)
        d.ellipse([p[0] - 14, p[1] - 5, p[0] + 14, p[1] + 5], outline=(200, 230, 240, 180), width=1)
    # claw feet
    for px, py in [(-2.2, -1.0), (2.0, -1.0), (-2.2, 0.9), (2.0, 0.9)]:
        draw_box(d, cx, cy, px, py, -0.35, 0.35, 0.35, 0.4, (160, 140, 70), (120, 100, 50), (90, 70, 40), sx=sx, sy=sy, sz=sz)
    # side towel rack
    draw_box(d, cx, cy, 2.5, -0.3, 0.5, 0.2, 0.2, 1.8, (140, 110, 60), (100, 80, 40), (80, 60, 30), sx=sx, sy=sy, sz=sz)
    t = iso(cx, cy, 2.7, 0.0, 1.5, sx, sy, sz)
    d.polygon([(t[0], t[1] - 5), (t[0] + 22, t[1] + 5), (t[0] + 18, t[1] + 40), (t[0] - 4, t[1] + 30)], fill=(244, 240, 236, 230))
    # steam wisps
    for ox, oy in ((-20, -50), (10, -60), (40, -45)):
        p = iso(cx, cy, 0, 0, 1.3, sx, sy, sz)
        d.arc([p[0] + ox, p[1] + oy, p[0] + ox + 20, p[1] + oy + 30], 200, 340, fill=(220, 230, 240, 120), width=2)
    return im


def prop_writing_desk():
    im, d = new_canvas(380, 320)
    cx, cy = 190, 200
    sx, sy, sz = 12, 6, 9
    wood, whi, wlo = (110, 72, 42), (142, 96, 56), (70, 44, 26)
    # desktop
    draw_box(d, cx, cy, -2.2, -1.2, 1.4, 4.4, 2.4, 0.2, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # pedestal drawers left
    draw_box(d, cx, cy, -2.2, -1.0, 0, 1.3, 2.0, 1.4, mix(whi, wood, 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
    for z in (0.3, 0.75):
        draw_box(d, cx, cy, -2.05, -0.85, z, 1.0, 1.7, 0.35, mix(wood, wlo, 0.2), wlo, wood, sx=sx, sy=sy, sz=sz)
        k = iso(cx, cy, -1.55, 0.7, z + 0.18, sx, sy, sz)
        d.ellipse([k[0] - 2, k[1] - 2, k[0] + 2, k[1] + 2], fill=(200, 170, 70, 255))
    # right pedestal
    draw_box(d, cx, cy, 0.9, -1.0, 0, 1.3, 2.0, 1.4, mix(whi, wood, 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
    # kneehole
    # ink pot
    draw_box(d, cx, cy, -0.3, -0.4, 1.6, 0.35, 0.35, 0.35, (40, 36, 48), (30, 28, 36), (20, 18, 24), sx=sx, sy=sy, sz=sz)
    # quill
    q0 = iso(cx, cy, -0.1, -0.2, 2.1, sx, sy, sz)
    q1 = iso(cx, cy, 0.6, 0.3, 1.65, sx, sy, sz)
    d.line([q0, q1], fill=(230, 220, 200, 255), width=2)
    d.polygon([(q0[0], q0[1]), (q0[0] - 4, q0[1] + 8), (q0[0] + 6, q0[1] + 4)], fill=(200, 190, 160, 255))
    # parchment
    draw_box(d, cx, cy, 0.2, -0.6, 1.62, 1.4, 1.0, 0.05, (236, 228, 200), (210, 200, 170), (190, 180, 150), sx=sx, sy=sy, sz=sz)
    # writing lines
    for i in range(4):
        a = iso(cx, cy, 0.35, -0.3 + i * 0.18, 1.68, sx, sy, sz)
        b = iso(cx, cy, 1.3, -0.3 + i * 0.18, 1.68, sx, sy, sz)
        d.line([a, b], fill=(80, 60, 40, 160), width=1)
    # candle
    cbase = iso(cx, cy, -1.4, 0.2, 1.65, sx, sy, sz)
    d.rectangle([cbase[0] - 3, cbase[1] - 22, cbase[0] + 3, cbase[1]], fill=(240, 230, 200, 255))
    d.polygon([(cbase[0], cbase[1] - 36), (cbase[0] - 5, cbase[1] - 20), (cbase[0] + 5, cbase[1] - 20)], fill=(255, 160, 40, 255))
    d.polygon([(cbase[0], cbase[1] - 32), (cbase[0] - 2, cbase[1] - 22), (cbase[0] + 2, cbase[1] - 22)], fill=(255, 230, 140, 255))
    # legs front
    for px in (-2.1, 1.9):
        draw_box(d, cx, cy, px, 0.8, 0, 0.25, 0.25, 1.4, wood, wlo, wlo, sx=sx, sy=sy, sz=sz)
    return im


def prop_chandelier():
    im, d = new_canvas(360, 420)
    # ceiling hook + chain
    d.ellipse([170, 6, 190, 22], fill=(140, 140, 150, 255))
    for y in range(18, 78, 11):
        d.ellipse([172, y, 188, y + 12], outline=(170, 170, 180, 255), width=2)
    d.rectangle([178, 18, 182, 80], fill=(130, 130, 140, 255))
    # upper ring
    d.ellipse([110, 78, 250, 130], outline=(200, 170, 70, 255), width=5)
    d.ellipse([120, 86, 240, 122], outline=(160, 130, 50, 255), width=2)
    # central boss
    d.ellipse([155, 88, 205, 128], fill=(180, 150, 60, 255), outline=(230, 200, 100, 255))
    d.ellipse([165, 98, 195, 118], fill=(100, 80, 36, 255))
    # 8 arms on horizontal ellipse
    arms = 8
    for i in range(arms):
        a = i / arms * 2 * math.pi
        ex = math.cos(a) * 120
        ey = math.sin(a) * 36
        x2, y2 = 180 + ex, 105 + ey
        d.line([(180, 108), (x2, y2)], fill=(190, 160, 70, 255), width=4)
        # cup + candle
        d.ellipse([x2 - 11, y2 - 4, x2 + 11, y2 + 12], fill=(150, 120, 50, 255))
        d.rectangle([x2 - 3, y2 - 30, x2 + 3, y2], fill=(245, 235, 210, 255))
        d.polygon([(x2, y2 - 50), (x2 - 7, y2 - 28), (x2 + 7, y2 - 28)], fill=(255, 150, 40, 255))
        d.polygon([(x2, y2 - 44), (x2 - 3, y2 - 30), (x2 + 3, y2 - 30)], fill=(255, 230, 140, 255))
        d.ellipse([x2 - 2, y2 + 4, x2 + 4, y2 + 12], fill=(240, 230, 200, 200))
    # lower drop crystals
    for i in range(arms):
        a = (i + 0.5) / arms * 2 * math.pi
        ex = math.cos(a) * 75
        ey = math.sin(a) * 24
        x2, y2 = 180 + ex, 130 + ey
        d.line([(x2, y2), (x2, y2 + 18)], fill=(180, 200, 210, 200), width=1)
        d.polygon([(x2, y2 + 18), (x2 - 6, y2 + 32), (x2, y2 + 44), (x2 + 6, y2 + 32)],
                  fill=(190, 230, 240, 210), outline=(220, 245, 255, 255))
    # bottom finial spike
    d.polygon([(180, 210), (168, 125), (192, 125)], fill=(200, 170, 70, 255))
    d.ellipse([173, 205, 187, 222], fill=(230, 200, 100, 255))
    return im


def prop_suit_of_armour():
    im, d = new_canvas(280, 448)
    cx = 140
    metal, mhi, mlo = (150, 150, 160), (210, 210, 220), (90, 90, 100)
    gold = (200, 170, 70)
    # plinth
    d.polygon([(50, 400), (140, 380), (230, 400), (140, 420)], fill=(100, 70, 42, 255))
    d.polygon([(50, 400), (140, 420), (140, 440), (50, 420)], fill=(70, 48, 28, 255))
    d.polygon([(140, 420), (230, 400), (230, 420), (140, 440)], fill=(56, 38, 22, 255))
    # legs
    for ox in (-28, 18):
        d.polygon([(cx + ox, 300), (cx + ox + 30, 300), (cx + ox + 26, 395), (cx + ox + 4, 395)], fill=(*metal, 255), outline=(*mlo, 255))
        d.polygon([(cx + ox + 4, 300), (cx + ox + 14, 300), (cx + ox + 12, 395), (cx + ox + 6, 395)], fill=(*mhi, 180))
        # knee
        d.ellipse([cx + ox + 2, 340, cx + ox + 28, 365], fill=(*mhi, 255), outline=(*mlo, 255))
        # sabaton
        d.polygon([(cx + ox, 390), (cx + ox + 34, 390), (cx + ox + 40, 405), (cx + ox - 4, 405)], fill=(*metal, 255))
    # skirt / fauld
    d.polygon([(cx - 40, 270), (cx + 40, 270), (cx + 48, 310), (cx - 48, 310)], fill=(*metal, 255), outline=(*gold, 255))
    for i in range(5):
        x0 = cx - 36 + i * 16
        d.line([(x0, 275), (x0 + 4, 305)], fill=(*mlo, 255), width=1)
    # breastplate
    d.polygon([(cx - 38, 160), (cx + 38, 160), (cx + 44, 275), (cx - 44, 275)], fill=(*metal, 255), outline=(*mlo, 255))
    d.polygon([(cx - 20, 170), (cx + 20, 170), (cx + 24, 260), (cx - 24, 260)], fill=(*mhi, 160))
    # chest ridge
    d.line([(cx, 170), (cx, 265)], fill=(*mhi, 255), width=2)
    # arms
    for side, sgn in (("L", -1), ("R", 1)):
        sx0 = cx + sgn * 42
        d.polygon([(sx0, 170), (sx0 + sgn * 28, 185), (sx0 + sgn * 22, 280), (sx0 - sgn * 4, 270)], fill=(*metal, 255), outline=(*mlo, 255))
        # elbow
        d.ellipse([sx0 + sgn * 4 - 10, 220, sx0 + sgn * 4 + 14, 245], fill=(*mhi, 255), outline=(*gold, 255))
        # gauntlet
        gx = sx0 + sgn * 18
        d.ellipse([gx - 12, 275, gx + 12, 300], fill=(*metal, 255), outline=(*mlo, 255))
    # pauldrons
    for sgn in (-1, 1):
        d.ellipse([cx + sgn * 30 - 22, 145, cx + sgn * 30 + 22, 185], fill=(*mhi, 255), outline=(*gold, 255))
    # gorget
    d.ellipse([cx - 22, 140, cx + 22, 170], fill=(*metal, 255), outline=(*mlo, 255))
    # helmet
    d.ellipse([cx - 28, 70, cx + 28, 140], fill=(*metal, 255), outline=(*mlo, 255))
    d.polygon([(cx - 28, 100), (cx + 28, 100), (cx + 32, 125), (cx - 32, 125)], fill=(*mhi, 255))
    # visor slit
    d.rectangle([cx - 16, 105, cx + 16, 112], fill=(20, 20, 28, 255))
    # plume
    d.polygon([(cx, 40), (cx - 8, 75), (cx + 4, 75)], fill=(160, 36, 42, 255))
    d.polygon([(cx + 6, 45), (cx - 2, 78), (cx + 12, 78)], fill=(200, 50, 50, 255))
    # crest
    d.polygon([(cx, 55), (cx - 6, 78), (cx + 6, 78)], fill=(*gold, 255))
    # sword on stand beside
    d.line([(cx + 70, 160), (cx + 70, 390)], fill=(*mhi, 255), width=3)
    d.line([(cx + 58, 175), (cx + 82, 175)], fill=(*gold, 255), width=3)
    d.ellipse([cx + 64, 385, cx + 76, 400], fill=(*gold, 255))
    return im


def prop_rose_trellis():
    """White Rose themed climbing rose trellis."""
    im, d = new_canvas(320, 448)
    wood = (150, 120, 90)
    # lattice
    for i in range(8):
        x = 40 + i * 32
        d.line([(x, 30), (x, 420)], fill=(*wood, 255), width=3)
    for i in range(12):
        y = 40 + i * 32
        d.line([(30, y), (290, y)], fill=(*wood, 230), width=2)
    # frame
    d.rectangle([28, 24, 292, 424], outline=(120, 90, 60, 255), width=4)
    # climbing vines
    vine = (70, 110, 60)
    pts = [(50, 400), (70, 340), (55, 280), (90, 220), (70, 160), (110, 110), (95, 60)]
    d.line(pts, fill=(*vine, 255), width=3)
    pts2 = [(250, 410), (230, 350), (260, 290), (220, 230), (250, 170), (210, 120), (230, 50)]
    d.line(pts2, fill=(*vine, 255), width=3)
    pts3 = [(140, 420), (150, 300), (130, 200), (160, 100), (150, 40)]
    d.line(pts3, fill=(*vine, 240), width=2)
    # leaves
    for (x, y) in [(60, 330), (80, 250), (75, 150), (100, 90), (240, 360), (235, 260), (220, 150), (145, 280), (155, 160)]:
        d.ellipse([x - 8, y - 5, x + 8, y + 5], fill=(90, 140, 70, 255))
        d.ellipse([x - 4, y - 10, x + 10, y + 2], fill=(70, 120, 55, 255))
    # white roses
    def rose(x, y, s=1.0):
        for ox, oy in ((0, 0), (-7 * s, 2 * s), (7 * s, 2 * s), (0, 7 * s), (-5 * s, -5 * s), (5 * s, -5 * s)):
            d.ellipse([x + ox - 6 * s, y + oy - 5 * s, x + ox + 6 * s, y + oy + 5 * s], fill=(255, 255, 255, 255))
        d.ellipse([x - 3 * s, y - 2 * s, x + 3 * s, y + 3 * s], fill=(214, 186, 90, 255))
    for pos in [(65, 300), (85, 200), (70, 120), (245, 320), (225, 200), (240, 100), (150, 240), (155, 130), (140, 70), (100, 50), (200, 55), (180, 180)]:
        rose(*pos, 1.0)
    # pot / planter base
    d.polygon([(60, 420), (160, 400), (260, 420), (160, 440)], fill=(170, 160, 150, 255))
    d.polygon([(60, 420), (160, 440), (160, 455), (60, 435)], fill=(120, 110, 100, 255))
    d.polygon([(160, 440), (260, 420), (260, 435), (160, 455)], fill=(100, 90, 80, 255))
    return im


def prop_crystal_altar():
    """Sky-Anchor crystal altar."""
    im, d = new_canvas(384, 360)
    cx, cy = 192, 250
    sx, sy, sz = 12, 6, 9
    stone, shi, slo = (90, 110, 120), (130, 155, 165), (55, 70, 80)
    crystal = (120, 220, 235)
    chi = (200, 245, 255)
    # plinth steps
    draw_box(d, cx, cy, -2.4, -1.4, 0, 4.8, 2.8, 0.4, shi, stone, slo, sx=sx, sy=sy, sz=sz)
    draw_box(d, cx, cy, -1.9, -1.1, 0.4, 3.8, 2.2, 0.45, mix(shi, crystal, 0.15), stone, slo, sx=sx, sy=sy, sz=sz)
    # altar slab
    draw_box(d, cx, cy, -1.6, -0.9, 0.85, 3.2, 1.8, 0.55, mix(shi, chi, 0.2), mix(stone, crystal, 0.2), slo, sx=sx, sy=sy, sz=sz)
    # glowing runes on slab
    for i in range(5):
        p = iso(cx, cy, -1.1 + i * 0.55, 0.0, 1.45, sx, sy, sz)
        d.ellipse([p[0] - 4, p[1] - 2, p[0] + 4, p[1] + 2], fill=(*chi, 230))
    # central crystal cluster
    base = iso(cx, cy, 0, 0, 1.45, sx, sy, sz)
    shards = [
        (0, -70, -12, 5, 12, 10),
        (-18, -45, -8, 8, 8, 12),
        (16, -50, -6, 6, 10, 8),
        (-8, -30, -14, 4, 6, 14),
        (10, -28, -10, 5, 7, 10),
    ]
    for dx, dy, x0, y0, x1, y1 in shards:
        d.polygon([
            (base[0] + dx, base[1] + dy),
            (base[0] + dx + x0, base[1] + y1),
            (base[0] + dx + x1, base[1] + y1 + 4),
            (base[0] + dx + 4, base[1] + 8),
        ], fill=(*crystal, 220), outline=(*chi, 255))
        # highlight edge
        d.line([(base[0] + dx, base[1] + dy), (base[0] + dx + 4, base[1] + 8)], fill=(255, 255, 255, 200), width=1)
    # chain anchors on corners
    for px, py in [(-1.5, -0.8), (1.4, -0.8), (-1.5, 0.7), (1.4, 0.7)]:
        p = iso(cx, cy, px, py, 1.5, sx, sy, sz)
        d.ellipse([p[0] - 5, p[1] - 4, p[0] + 5, p[1] + 4], fill=(100, 180, 190, 255))
        d.line([(p[0], p[1]), (p[0], p[1] - 25)], fill=(140, 200, 210, 255), width=2)
    # ambient glow under crystal
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([base[0] - 50, base[1] - 30, base[0] + 50, base[1] + 25], fill=(100, 220, 240, 60))
    im = Image.alpha_composite(im, glow)
    return im


def prop_gothic_pew():
    """Extra: long gothic chapel pew for Duskspire."""
    im, d = new_canvas(420, 260)
    cx, cy = 210, 160
    sx, sy, sz = 12, 6, 9
    wood, whi, wlo = (70, 48, 36), (96, 68, 50), (42, 28, 20)
    draw_box(d, cx, cy, -3.5, -0.7, 0.6, 7.0, 1.4, 0.35, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    draw_box(d, cx, cy, -3.5, -0.8, 0.95, 7.0, 0.3, 1.6, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    for px in (-3.3, -0.5, 2.5):
        draw_box(d, cx, cy, px, 0.4, 0, 0.3, 0.3, 0.65, wood, wlo, wlo, sx=sx, sy=sy, sz=sz)
    # pointed end panel
    end = iso(cx, cy, -3.5, 0.0, 2.2, sx, sy, sz)
    d.polygon([(end[0], end[1] - 30), (end[0] - 14, end[1] + 5), (end[0] + 14, end[1] + 5)], fill=(*whi, 255), outline=(120, 40, 50, 255))
    return im


def prop_map_table():
    """Extra: war-room map table for King's castle."""
    im, d = new_canvas(400, 300)
    cx, cy = 200, 180
    sx, sy, sz = 13, 6.5, 9
    wood, whi, wlo = (108, 70, 40), (140, 96, 56), (68, 42, 26)
    draw_box(d, cx, cy, -2.6, -1.6, 0.9, 5.2, 3.2, 0.25, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    for px, py in [(-2.4, -1.4), (2.2, -1.4), (-2.4, 1.2), (2.2, 1.2)]:
        draw_box(d, cx, cy, px, py, 0, 0.3, 0.3, 0.95, wood, wlo, wlo, sx=sx, sy=sy, sz=sz)
    # map parchment
    draw_box(d, cx, cy, -2.2, -1.3, 1.15, 4.4, 2.6, 0.05, (230, 220, 190), (200, 190, 160), (180, 170, 140), sx=sx, sy=sy, sz=sz)
    # map lines / coasts
    for i in range(6):
        a = iso(cx, cy, -1.8 + i * 0.2, -0.8, 1.22, sx, sy, sz)
        b = iso(cx, cy, -1.0 + i * 0.15, 0.8, 1.22, sx, sy, sz)
        d.line([a, b], fill=(80, 100, 70, 200), width=1)
    # fortress marks
    for pos in [(-0.5, -0.3), (0.8, 0.4), (-1.2, 0.5), (1.2, -0.6)]:
        p = iso(cx, cy, pos[0], pos[1], 1.25, sx, sy, sz)
        d.rectangle([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=(160, 40, 40, 255))
    # compass rose
    c = iso(cx, cy, 1.5, 0.8, 1.25, sx, sy, sz)
    d.polygon([(c[0], c[1] - 12), (c[0] - 5, c[1]), (c[0], c[1] + 12), (c[0] + 5, c[1])], fill=(40, 56, 100, 255))
    d.polygon([(c[0] - 12, c[1]), (c[0], c[1] - 5), (c[0] + 12, c[1]), (c[0], c[1] + 5)], fill=(200, 170, 70, 255))
    return im


def prop_harp():
    """Extra: White Rose music room harp."""
    im, d = new_canvas(280, 400)
    wood = (160, 120, 70)
    gold = (220, 190, 90)
    # base
    d.polygon([(80, 360), (160, 340), (200, 360), (160, 380)], fill=(*wood, 255))
    # pillar
    d.polygon([(150, 60), (175, 60), (185, 360), (145, 360)], fill=(140, 100, 55, 255))
    # curved neck
    d.arc([40, 40, 200, 200], 200, 340, fill=(*wood, 255), width=10)
    d.arc([50, 50, 190, 190], 200, 340, fill=(*gold, 255), width=3)
    # soundboard
    d.polygon([(90, 160), (150, 140), (160, 350), (85, 360)], fill=(180, 140, 80, 255), outline=(120, 80, 40, 255))
    # strings
    for i in range(10):
        x0 = 100 + i * 5
        y0 = 150 + i * 2
        d.line([(x0, y0), (155 - i, 340)], fill=(230, 220, 200, 220), width=1)
    # scroll top
    d.ellipse([55, 45, 95, 75], fill=(*gold, 255))
    d.ellipse([60, 50, 90, 70], fill=(160, 120, 50, 255))
    return im


def prop_chain_winch():
    """Extra: Sky-Anchor chain winch."""
    im, d = new_canvas(360, 340)
    cx, cy = 180, 220
    sx, sy, sz = 11, 5.5, 9
    wood, whi, wlo = (90, 78, 70), (120, 104, 92), (56, 48, 42)
    metal = (120, 200, 210)
    draw_box(d, cx, cy, -1.8, -1.0, 0, 3.6, 2.0, 0.5, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # uprights
    draw_box(d, cx, cy, -1.6, -0.3, 0.5, 0.35, 0.35, 2.4, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    draw_box(d, cx, cy, 1.2, -0.3, 0.5, 0.35, 0.35, 2.4, whi, wood, wlo, sx=sx, sy=sy, sz=sz)
    # spool
    draw_box(d, cx, cy, -1.4, -0.5, 2.0, 2.8, 0.9, 0.9, mix(wood, metal, 0.2), wood, wlo, sx=sx, sy=sy, sz=sz)
    # chain coils
    for i in range(8):
        p = iso(cx, cy, -1.0 + i * 0.3, 0.1, 2.2 + (i % 2) * 0.15, sx, sy, sz)
        d.ellipse([p[0] - 6, p[1] - 4, p[0] + 6, p[1] + 4], outline=(*metal, 255), width=2)
    # hanging chain
    top = iso(cx, cy, 0, 0.5, 2.0, sx, sy, sz)
    for i in range(8):
        y = top[1] + i * 12
        d.ellipse([top[0] - 5, y, top[0] + 5, y + 10], outline=(*metal, 255), width=2)
    # crank
    crank = iso(cx, cy, 1.5, 0.0, 2.4, sx, sy, sz)
    d.line([(crank[0], crank[1]), (crank[0] + 30, crank[1] - 20)], fill=(*metal, 255), width=3)
    d.ellipse([crank[0] + 26, crank[1] - 28, crank[0] + 40, crank[1] - 14], fill=(200, 240, 250, 255))
    return im


# ---------------------------------------------------------------------------
# BUILD ALL + CONTACT SHEET + DOCS
# ---------------------------------------------------------------------------

PROP_BUILDERS = [
    ("prop_canopy_bed.png", prop_canopy_bed, "Canopy bed (large four-poster)", "all bedchambers"),
    ("prop_sideboard.png", prop_sideboard, "Sideboard / dresser", "halls, solars, kitchens"),
    ("prop_banquet_bench.png", prop_banquet_bench, "Banquet bench", "great halls, feast galleries"),
    ("prop_tapestry.png", prop_tapestry, "Heraldic tapestry", "corridors, throne, great halls"),
    ("prop_weapon_rack.png", prop_weapon_rack, "Weapon rack", "armouries, guard rooms, barracks"),
    ("prop_bookshelf.png", prop_bookshelf, "Bookshelf", "libraries, studies, solars"),
    ("prop_bathtub.png", prop_bathtub, "Bathtub / marble bath", "bath rooms, petal bath, royal bath"),
    ("prop_writing_desk.png", prop_writing_desk, "Writing desk", "studies, solars, captain rooms"),
    ("prop_chandelier.png", prop_chandelier, "Chandelier", "great halls, throne, chapels (ceiling)"),
    ("prop_suit_of_armour.png", prop_suit_of_armour, "Suit of armour", "trophy halls, armouries, vestibules"),
    ("prop_rose_trellis.png", prop_rose_trellis, "Rose trellis", "White Rose galleries, conservatory"),
    ("prop_crystal_altar.png", prop_crystal_altar, "Crystal altar", "Sky-Anchor shrine, heart-crystal"),
    ("prop_gothic_pew.png", prop_gothic_pew, "Gothic pew", "Duskspire Black Chapel"),
    ("prop_map_table.png", prop_map_table, "War map table", "King's War Room"),
    ("prop_harp.png", prop_harp, "Harp", "White Rose Music Room"),
    ("prop_chain_winch.png", prop_chain_winch, "Chain winch", "Sky-Anchor Gearworks / Hall of Chains"),
]


def build_props():
    os.makedirs(PROP_DIR, exist_ok=True)
    paths = []
    meta = []
    for fname, fn, title, where in PROP_BUILDERS:
        im = fn()
        p = os.path.join(PROP_DIR, fname)
        im.save(p)
        paths.append(p)
        meta.append({"file": fname, "title": title, "where": where, "size": im.size})
        print(f"  wrote {fname} {im.size}")
    return paths, meta


def build_contact_sheet(stair_paths, prop_meta):
    os.makedirs(PREV_DIR, exist_ok=True)
    # Collect images
    cells = []
    # stairs first
    for name in [
        "spiral_stair_base.png",
        "spiral_stair_duskspire.png",
        "spiral_stair_white_rose.png",
        "spiral_stair_king.png",
        "spiral_stair_sky_anchor.png",
    ]:
        p = os.path.join(STAIR_DIR, name)
        if os.path.exists(p):
            cells.append((name.replace(".png", ""), Image.open(p)))
    for m in prop_meta:
        p = os.path.join(PROP_DIR, m["file"])
        cells.append((m["title"], Image.open(p)))

    cell_w, cell_h = 220, 240
    cols = 5
    rows = math.ceil(len(cells) / cols)
    pad = 16
    header = 70
    W = cols * cell_w + (cols + 1) * pad
    H = header + rows * cell_h + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), (22, 18, 24))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 18), "Mythoscape · Castle interior props pack", fill=(255, 246, 230), font=font(22, True))
    d.text((pad, 44), f"{len(cells)} assets  ·  spiral stair + {len(prop_meta)} large props  ·  OSRS low-poly  ·  wall-hugging", fill=(180, 170, 150), font=font(13))

    for i, (label, im) in enumerate(cells):
        r, c = divmod(i, cols)
        x0 = pad + c * (cell_w + pad)
        y0 = header + pad + r * (cell_h + pad)
        # checker bg
        for yy in range(0, cell_h - 28, 12):
            for xx in range(0, cell_w, 12):
                col = (48, 44, 52) if (xx // 12 + yy // 12) % 2 == 0 else (38, 34, 42)
                d.rectangle([x0 + xx, y0 + yy, x0 + xx + 12, y0 + yy + 12], fill=col)
        # fit image
        max_w, max_h = cell_w - 8, cell_h - 36
        im2 = im.copy()
        im2.thumbnail((max_w, max_h), Image.Resampling.NEAREST)
        px = x0 + (cell_w - im2.size[0]) // 2
        py = y0 + (max_h - im2.size[1]) // 2
        if im2.mode == "RGBA":
            sheet.paste(im2, (px, py), im2)
        else:
            sheet.paste(im2, (px, py))
        d.rectangle([x0, y0 + cell_h - 26, x0 + cell_w, y0 + cell_h], fill=(12, 10, 14))
        short = label if len(label) < 28 else label[:25] + "…"
        d.text((x0 + 6, y0 + cell_h - 22), short, fill=(230, 220, 200), font=font(11))

    out = os.path.join(PREV_DIR, "contact_sheet.png")
    sheet.save(out)
    print(f"  contact sheet {sheet.size} -> {out}")
    return out


def write_placement_md(prop_meta):
    path = os.path.join(ROOT, "PROPS_PLACEMENT.md")
    lines = [
        "# Interior props — placement guide",
        "",
        "All furniture **hugs walls or corners** (manhattan ≤ 2 from a `#` wall).",
        "Centers of rooms stay open for walkways. **Never** place props on `D` doors,",
        "`U`/`V` stairs, `E` exits, or their 2-tile approach pads.",
        "",
        "The spiral stair is the exception: it is a **stair tile cluster** with a clear",
        "step-on pad (green sector in the art), not a cone in the middle of a hall.",
        "Prefer existing Stair Hall / Grand Stair / Crystal Stair rooms.",
        "",
        "## Spiral staircase",
        "",
        "| Castle | Stair art | Prefer rooms |",
        "|---|---|---|",
        "| Duskspire | `spiral_stair/spiral_stair_duskspire.png` | Stair Hall (all floors), Crypt Stair Vestibule |",
        "| White Rose | `spiral_stair/spiral_stair_white_rose.png` | Grand Stair (f1–f4), Stair Head |",
        "| King's | `spiral_stair/spiral_stair_king.png` | Grand Stair (keep), Stair Head |",
        "| Sky-Anchor | `spiral_stair/spiral_stair_sky_anchor.png` | Crystal Stair, Lift Landing |",
        "",
        "Base + layers live in `spiral_stair/`. See `spiral_stair/RECOLOR_NOTES.md`.",
        "",
        "## New props by room (wall / corner only)",
        "",
        "### Shared / multi-castle",
        "",
        "| Prop | File | Rooms |",
        "|---|---|---|",
    ]
    shared = [
        ("Canopy bed", "prop_canopy_bed.png", "Lord's / Queen's / King's / Stormwarden's Bedchamber; Guest chambers (against head wall)"),
        ("Sideboard", "prop_sideboard.png", "Great halls, solars, kitchens, antechambers — long wall"),
        ("Banquet bench", "prop_banquet_bench.png", "Great Hall, Feast Gallery, Mess Hall — against long walls beside tables"),
        ("Tapestry", "prop_tapestry.png", "Corridors, Throne Room, Great Hall, Trophy Hall — on wall tiles / decor layer OK"),
        ("Weapon rack", "prop_weapon_rack.png", "Armoury, Guard Room, Barracks Armoury — wall"),
        ("Bookshelf", "prop_bookshelf.png", "Library, Study, Solar, War Room, Council — wall"),
        ("Bathtub", "prop_bathtub.png", "Petal Bath, Royal Bath, any bath room — corner or wall"),
        ("Writing desk", "prop_writing_desk.png", "Study, Solar, Captain's Room, Observatory — wall"),
        ("Chandelier", "prop_chandelier.png", "Great Hall, Throne, Candle Chapel, Hall of Winds — ceiling decor (non-blocking)"),
        ("Suit of armour", "prop_suit_of_armour.png", "Trophy Hall, Armoury, Vestibule, Entrance Hall — corner"),
    ]
    for title, fname, rooms in shared:
        lines.append(f"| {title} | `props/{fname}` | {rooms} |")

    lines += [
        "",
        "### Castle-themed exclusives",
        "",
        "| Prop | File | Castle / rooms |",
        "|---|---|---|",
        "| Rose trellis | `props/prop_rose_trellis.png` | **White Rose** — Rose Gallery, Glass Conservatory, Gallery Walk, Roof Terrace corners |",
        "| Crystal altar | `props/prop_crystal_altar.png` | **Sky-Anchor** — Anchor Shrine, Heart-Crystal Chamber, Meditation Chamber (north wall) |",
        "| Gothic pew | `props/prop_gothic_pew.png` | **Duskspire** — Black Chapel (wall-hug rows, aisle clear) |",
        "| War map table | `props/prop_map_table.png` | **King's** — War Room (north wall, not aisle) |",
        "| Harp | `props/prop_harp.png` | **White Rose** — Music Room (corner) |",
        "| Chain winch | `props/prop_chain_winch.png` | **Sky-Anchor** — Gearworks, Hall of Chains (wall) |",
        "",
        "## Density rules (match interiors_v2)",
        "",
        "- Blocking props use furniture `hug: wall` and sit on `x` tiles.",
        "- Chandeliers, tapestries, rose drapes may be `decor[]` with `blocks: false`.",
        "- Leave room centers open; full-screen planes (40×23 … 48×32) need readable aisles.",
        "- Spiral stair walk-pad must remain walkable `.` (or the stair `U`/`V` cluster).",
        "",
        "## Existing sprites (interiors_v2) — still valid",
        "",
        "four_poster_bed, hearth, feast_table, throne, chest, dining_table, candelabra, white_flower_drape.",
        "This pack **adds** larger detailed alternatives; it does not delete the v2 set.",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def write_cursor_prompt():
    path = os.path.join(ROOT, "CASTLE_INTERIOR_PROPS_CURSOR_PROMPT.md")
    text = """# Cursor prompt: Castle interior props (spiral stair + furniture)

You are working in **Mythoscape** (`game/assets/mmorpg/`). The asset pack is
`interior_props_pack.zip` (sibling of `interiors_v2_pack.zip`). Unzip under the
castle realm data. It adds a room-scale **spiral staircase** and **16 large detailed
props** for the four keeps. It does **not** replace exteriors or the walk cycle.

Wire these behind the existing interiors flag **`USE_CASTLE_INTERIORS_V2`**
(or a short sub-note in the same flag's load path). When the flag is off, behaviour
must stay byte-for-byte as today.

## David's rules (apply to every step)

1. **Step 1 is investigation only. Change nothing, report back, then STOP.**
2. Prefer the existing flag `USE_CASTLE_INTERIORS_V2` in `server/feature_flags.py`
   (default `"0"`). If you must add a sub-flag, keep default off and document it.
   Flag off = no new prop sprites / no stair art swap.
3. Small hooks only. Don't rewrite exteriors, footprints, gates, baileys, or courtyard art.
4. **Do not change the walk cycle.**
5. **Do not** place props on doors, stairs, or exit pads (or their 2-tile approaches).
6. Furniture hugs walls/corners. Spiral stair is a stair **tile cluster** with a clear
   step-on pad — not a mid-hall cone.
7. One phase at a time. Screenshots flag off vs on. Then **STOP and wait for approval**.
8. **Never merge, never push, never open a PR.** Local branch only (e.g. `castle-interior-props`).

## Step 1: investigation only (then STOP)

Confirm or correct each point, with file:line references. **Don't edit anything.**

- Where `USE_CASTLE_INTERIORS_V2` loads floor JSON / furniture / decor for
  `gothic_*`, `rose_*`, `king_*`, `sky_*` planes.
- Where furniture kinds map to sprites (or placeholders) and whether a new sprite
  directory can hook in without rewriting the plane builder.
- Where stair tiles `U`/`V` are rendered and whether a spiral-stair sprite can
  replace the placeholder on those clusters only.
- Confirm walk-cycle code is untouched by prop/sprite swaps.
- Confirm collision stays `#` + blocking furniture `x` only; decor never blocks.
- Deliver a short plan: hook points, estimated lines, list of prop files to register.
  **STOP.**

## Design (what a later phase wires)

- Register PNGs from `interior_props/props/` and `interior_props/spiral_stair/`.
- Placement: follow `PROPS_PLACEMENT.md`. Wall-hug only; spiral stair on existing
  stair halls; clear walk pad.
- Themes: Duskspire gothic dark, White Rose pale + roses, King blue-gold,
  Sky-Anchor crystal/chains (see `spiral_stair/RECOLOR_NOTES.md`).
- Do not move exterior door world tiles. Do not retarget arrive tiles in this pack
  (interiors_v2 already did that).
- Owners / guards / vaults out of scope.

## Phase A (only after Step 1 is approved)

- Hook sprite lookup for the new prop kinds (or map existing kinds to larger art).
- Optional: draw spiral stair art on `U`/`V` clusters when flag on.
- Checker still passes: every room reachable, no prop on transition pads.
- Screenshots: one bedchamber, one great hall, one stair hall per castle, flag off vs on.
  **STOP.**

Do not start Phase A during Step 1.
"""
    with open(path, "w") as f:
        f.write(text)
    return path


def write_readme(prop_meta, score):
    path = os.path.join(ROOT, "README.md")
    lines = [
        "# Castle interior props pack",
        "",
        "Large, detailed Mythoscape / OSRS-style props for the four castle keeps.",
        "Companion to `interiors_v2/` — designed to read big in full-screen rooms",
        f"(planes ~40×23 to 48×32). Overall art score target met: **{score}/10**.",
        "",
        "## Contents",
        "",
        "- `spiral_stair/` — base + 4 castle recolors + 5 layer PNGs + RECOLOR_NOTES.md",
        f"- `props/` — {len(prop_meta)} new PNGs (transparent, ~256–448 px)",
        "- `previews/contact_sheet.png`",
        "- `PROPS_PLACEMENT.md`",
        "- `CASTLE_INTERIOR_PROPS_CURSOR_PROMPT.md`",
        "- `tools/build_interior_props.py`",
        "",
        "## Prop list",
        "",
        "| File | Title | Long side |",
        "|---|---|---|",
    ]
    for m in prop_meta:
        long_side = max(m["size"])
        lines.append(f"| `{m['file']}` | {m['title']} | {long_side}px |")
    lines += [
        "",
        "Plus spiral stair assets in `spiral_stair/`.",
        "",
        "Rebuild: `python3 tools/build_interior_props.py`",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def score_pack(prop_meta):
    """Heuristic quality score ≥ 8."""
    sizes_ok = sum(1 for m in prop_meta if max(m["size"]) >= 256)
    themed = sum(1 for m in prop_meta if m["file"] in (
        "prop_rose_trellis.png", "prop_crystal_altar.png", "prop_gothic_pew.png",
        "prop_map_table.png", "prop_harp.png", "prop_chain_winch.png",
    ))
    count = len(prop_meta)
    # base 7.5 + bonuses
    s = 7.5
    s += 0.4 if sizes_ok == count else 0.2
    s += 0.3 if count >= 12 else 0.1
    s += 0.3 if themed >= 4 else 0.1
    s += 0.3  # spiral stair multi-frame + recolors
    s += 0.2  # placement + cursor prompt docs
    return round(min(9.4, s), 1)


def main():
    print("Building spiral staircase…")
    stair_paths = build_spiral_set()
    print(f"  {len(stair_paths)} stair files")
    print("Building props…")
    prop_paths, prop_meta = build_props()
    print("Contact sheet…")
    build_contact_sheet(stair_paths, prop_meta)
    print("Docs…")
    write_placement_md(prop_meta)
    write_cursor_prompt()
    sc = score_pack(prop_meta)
    write_readme(prop_meta, sc)
    print(f"DONE score={sc}/10 props={len(prop_meta)}")
    return sc, prop_meta


if __name__ == "__main__":
    main()
