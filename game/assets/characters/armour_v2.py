"""
armour_v2.py — bulk + ornament layer for USE_NEW_CHARACTERS.

Draws EXTRA shapes around the rig joints handed in by rs_humanoid_v2
(never moves a joint): broad breastplates, layered pauldrons, gauntlets,
faulds/tassets, knee cops, greaves, sabatons, capes and the high-tier
ornament (gold filigree, emblems, runes, gem inlays, time-based glow).
"""
import math
import pygame
import gear_v2 as gear

OUT = (30, 24, 22)
G = ((226, 182, 70), (150, 106, 34), (252, 224, 130))   # rich gold
fl = gear.fline

# Per-material ornament style (moderate for bronze..adamant, full for mythos/eclipse)
STYLE = {
    "bronze":  dict(trim=(112, 78, 40), rivet=(84, 58, 30), rivets=2, gold=False),
    "iron":    dict(trim=(66, 64, 66), rivet=(160, 158, 156), rivets=3, gold=False),
    "steel":   dict(trim=(214, 216, 222), rivet=(96, 98, 104), rivets=3, gold=False),
    "mithril": dict(trim=(196, 204, 226), rivet=(196, 204, 226), rivets=4, gold=False),
    "adamant": dict(trim=(176, 150, 84), rivet=(176, 150, 84), rivets=4, gold=False),
    "mythos":  dict(trim=G[0], rivet=G[2], rivets=4, gold=True, gem=(214, 30, 40), glow=(255, 96, 60)),
    "eclipse": dict(trim=G[0], rivet=G[2], rivets=4, gold=True, gem=(255, 176, 60), glow=(255, 206, 110)),
    "leather": dict(trim=(84, 56, 32), rivet=(170, 150, 110), rivets=3, gold=False),
    "goblin":  dict(trim=(70, 52, 30), rivet=(140, 120, 80), rivets=2, gold=False),
}


def st(look):
    return STYLE.get(look["mat"], STYLE["iron"]) if look else None


def bulk(look):
    if not look:
        return 0.0
    k = look["kind"]
    if k in ("platebody", "platelegs"):
        return 1.15 if look["tier"] >= 6 else 1.0
    if k in ("chainbody", "chainlegs"):
        return 0.7
    if k == "goblin_mail":
        return 0.6
    if k in ("leather_body", "chaps"):
        return 0.4
    return 0.0


def I(p):
    return (int(round(p[0])), int(round(p[1])))


def poly(surf, col, pts, outline=OUT, w=1):
    gear.fpoly(surf, col, pts, outline, w)


def trim(surf, pts, col, s, closed=True, w=0.42):
    pygame.draw.lines(surf, col, closed, [I(p) for p in pts], max(1, int(round(s * w))))


def dot(surf, col, c, r):
    pygame.draw.circle(surf, col, I(c), max(1, int(round(r))))


def glow(surf, c, r, col, t, base=0.55):
    """Additive soft glow, pulses with t (cosmetic only)."""
    a = base + 0.35 * math.sin(t * 2.6)
    R = max(2, int(r))
    g = pygame.Surface((R * 2 + 2, R * 2 + 2), pygame.SRCALPHA)
    for i in range(3):
        k = a * (0.35 + 0.3 * i)
        rr = max(1, int(R * (1.0 - 0.3 * i)))
        pygame.draw.circle(g, (int(col[0] * k * 0.5), int(col[1] * k * 0.5), int(col[2] * k * 0.5), 255), (R + 1, R + 1), rr)
    surf.blit(g, (int(c[0]) - R - 1, int(c[1]) - R - 1), special_flags=pygame.BLEND_RGB_ADD)


def gem(surf, c, r, col, t=None):
    dot(surf, OUT, c, r + 1)
    dot(surf, col, c, r)
    surf.set_at((int(c[0] - r * 0.35), int(c[1] - r * 0.35)), (255, 250, 230))
    if t is not None:
        glow(surf, c, r * 2.6, col, t)


RUNES = (((0, -1), (0, 1), (0, -1), (0.6, -0.4), (0, 0.1), (0.6, 0.5)),       # ᚱ-ish
         ((-0.5, -1), (-0.5, 1), (-0.5, -0.2), (0.5, -1), (-0.5, -0.2), (0.5, 1)),  # ᚴ-ish
         ((0, -1), (0, 1), (-0.6, -0.5), (0.6, 0.1), (-0.6, 0.1), (0.6, 0.7)),     # ᛉ-ish
         ((-0.5, 1), (0, -1), (0, -1), (0.5, 1), (-0.3, 0.2), (0.3, 0.2)))          # ᛏ/Λ
def rune(surf, c, h, col, idx=0):
    seg = RUNES[idx % len(RUNES)]
    for a, b in zip(seg[0::2], seg[1::2]):
        fl(surf, col, (c[0] + a[0] * h * 0.5, c[1] + a[1] * h * 0.5), (c[0] + b[0] * h * 0.5, c[1] + b[1] * h * 0.5), 1)


# ---------------------------------------------------------------------------
# Emblems
def eclipse_emblem(surf, c, r, t, bg=(40, 38, 46)):
    """Gold sun with 12 rays eclipsed by a dark crescent + amber core gem."""
    for i in range(12):
        a = i * math.pi / 6 + 0.13
        L = 1.5 if i % 2 == 0 else 1.22
        p1 = (c[0] + math.cos(a - 0.17) * r * 0.82, c[1] + math.sin(a - 0.17) * r * 0.82)
        p2 = (c[0] + math.cos(a) * r * L, c[1] + math.sin(a) * r * L)
        p3 = (c[0] + math.cos(a + 0.17) * r * 0.82, c[1] + math.sin(a + 0.17) * r * 0.82)
        pygame.draw.polygon(surf, G[0], [I(p1), I(p2), I(p3)])
    dot(surf, G[1], c, r * 0.9 + 1)
    dot(surf, G[0], c, r * 0.9)
    dot(surf, G[2], (c[0] - r * 0.3, c[1] - r * 0.3), r * 0.3)
    dot(surf, bg, (c[0] + r * 0.36, c[1] - r * 0.1), r * 0.72)          # the eclipse bite
    pygame.draw.circle(surf, G[1], I((c[0] + r * 0.36, c[1] - r * 0.1)), max(1, int(r * 0.72)), 1)
    gem(surf, (c[0] - r * 0.42, c[1] + r * 0.18), max(1, r * 0.22), (255, 176, 60), t)


def dragon_emblem(surf, c, r, t, bg=(146, 36, 34)):
    """Gold dragon head with spread wings, ruby eyes."""
    for sg in (-1, 1):
        wing = [(c[0] + sg * r * 0.4, c[1] - r * 0.1), (c[0] + sg * r * 1.2, c[1] - r * 1.0), (c[0] + sg * r * 2.1, c[1] - r * 0.85),
                (c[0] + sg * r * 1.8, c[1] - r * 0.3), (c[0] + sg * r * 1.95, c[1] + r * 0.2), (c[0] + sg * r * 1.45, c[1] + r * 0.05),
                (c[0] + sg * r * 1.4, c[1] + r * 0.6), (c[0] + sg * r * 0.5, c[1] + r * 0.45)]
        poly(surf, G[0], wing, G[1])
        for k in (0.9, 1.4):
            fl(surf, G[1], (c[0] + sg * r * 0.55, c[1] + r * 0.05), (c[0] + sg * r * (k + 0.3), c[1] - r * (0.7 if k < 1 else 0.5)), 1)
    head = [(c[0] - r * 0.55, c[1] - r * 0.75), (c[0] - r * 0.95, c[1] - r * 1.45), (c[0] - r * 0.35, c[1] - r * 0.95),
            (c[0] + r * 0.35, c[1] - r * 0.95), (c[0] + r * 0.95, c[1] - r * 1.45), (c[0] + r * 0.55, c[1] - r * 0.75),
            (c[0] + r * 0.6, c[1] + r * 0.1), (c[0] + r * 0.3, c[1] + r * 1.1), (c[0] - r * 0.3, c[1] + r * 1.1), (c[0] - r * 0.6, c[1] + r * 0.1)]
    poly(surf, G[0], head, G[1])
    poly(surf, G[2], [head[2], head[3], (c[0], c[1] + r * 0.5)], None)
    fl(surf, G[1], (c[0], c[1] - r * 0.4), (c[0], c[1] + r * 1.0), 1)
    for sg in (-1, 1):
        e = (c[0] + sg * r * 0.3, c[1] - r * 0.2)
        dot(surf, (230, 30, 40), e, max(1, r * 0.16))
        glow(surf, e, r * 0.55, (255, 70, 50), t, 0.4)


# ---------------------------------------------------------------------------
# Torso
def chest_plate(surf, s, neck, pelvis, chest_w, ww, shy, waist_y, look, view, t):
    b, d, l = look["pal"]
    S = st(look)
    cx = neck[0]
    top = neck[1] + 1.2 * s
    cw = chest_w * 0.95
    plate = [(cx - cw * 0.78, top), (cx + cw * 0.78, top), (cx + cw, shy + 1.2 * s), (cx + cw * 0.96, shy + 3.6 * s),
             (pelvis[0] + ww * 1.02, waist_y - 0.1 * s), (pelvis[0], waist_y + 0.9 * s), (pelvis[0] - ww * 1.02, waist_y - 0.1 * s),
             (cx - cw * 0.96, shy + 3.6 * s), (cx - cw, shy + 1.2 * s)]
    poly(surf, b, plate, None)
    poly(surf, d, [(cx + cw * 0.12, top), plate[1], plate[2], plate[3], plate[4], plate[5], (pelvis[0] + ww * 0.1, waist_y)], None)
    poly(surf, l, [(cx - cw * 0.7, top + 0.4 * s), (cx - cw * 0.1, top + 0.4 * s), (cx - cw * 0.25, shy + 2.8 * s), (cx - cw * 0.85, shy + 2.2 * s)], None)
    if view != "back":
        fl(surf, l, (cx, top + 0.3 * s), (cx, waist_y), max(1, int(s * 0.4)))           # keel
        # abdomen lames
        for k in (0.35, 0.68):
            y = shy + 3.6 * s + (waist_y - shy - 3.6 * s) * k
            fl(surf, d, (pelvis[0] - ww * 0.95, y), (pelvis[0] + ww * 0.95, y), 1)
            fl(surf, S["trim"], (pelvis[0] - ww * 0.95, y + 1), (pelvis[0] + ww * 0.95, y + 1), 1)
    trim(surf, plate, S["trim"], s, True, 0.45 if S["gold"] else 0.32)
    pygame.draw.lines(surf, OUT, True, [I(p) for p in plate], 1) if not S["gold"] else None
    # rivets along the neckline
    n = S["rivets"]
    for i in range(n):
        u = (i + 0.5) / n
        dot(surf, S["rivet"], (cx - cw * 0.66 + cw * 1.32 * u, top + 0.7 * s), 0.32 * s)
    if not S["gold"] or view == "back":
        if S["gold"]:
            for i in range(3):
                rune(surf, (cx + (i - 1) * 1.6 * s, shy + 5.2 * s), 1.6 * s, G[0], i)
        return
    # --- magnificent sets: double filigree, scrollwork, emblem, gems
    inner = [(cx + (p[0] - cx) * 0.84, shy + 2.2 * s + (p[1] - shy - 2.2 * s) * 0.86) for p in plate]
    pygame.draw.lines(surf, G[1], True, [I(p) for p in inner], 1)
    for sg in (-1, 1):   # scroll curls at the collar corners
        c0 = (cx + sg * cw * 0.6, top + 1.6 * s)
        pygame.draw.arc(surf, G[0], pygame.Rect(int(c0[0] - 0.9 * s), int(c0[1] - 0.9 * s), int(1.8 * s), int(1.8 * s)),
                        0 if sg > 0 else math.pi / 2, math.pi * 1.5 if sg > 0 else math.pi * 2, 1)
    ec = (cx, shy + 2.3 * s)
    if look["mat"] == "eclipse":
        eclipse_emblem(surf, ec, 1.75 * s, t, b)
        for sg in (-1, 1):
            gem(surf, (pelvis[0] + sg * ww * 0.55, waist_y - 0.9 * s), 0.38 * s, (150, 70, 220), t)
    else:
        dragon_emblem(surf, (ec[0], ec[1] + 0.2 * s), 1.45 * s, t, b)
        gem(surf, (pelvis[0], waist_y - 0.5 * s), 0.45 * s, (214, 30, 40), t)
    for i, sg in enumerate((-1, 1)):
        rune(surf, (pelvis[0] + sg * ww * 0.55, shy + 5.0 * s), 1.5 * s, G[2], i + 2)


def back_cape(surf, s, neck, pelvis, look, view, sway, t):
    """Emblem cape for mythos/eclipse bodies. side: behind body; back: over the backplate."""
    if not look or look["mat"] not in ("mythos", "eclipse"):
        return
    col = (96, 18, 22) if look["mat"] == "mythos" else (30, 24, 42)
    dk = tuple(max(0, v - 18) for v in col)
    top = neck[1] + 1.6 * s
    if view == "side":
        pts = [(neck[0] - 4.0 * s, top), (neck[0] + 1.0 * s, top), (pelvis[0] - 0.5 * s + sway, pelvis[1] + 9.5 * s),
               (pelvis[0] - 6.0 * s + sway * 0.4, pelvis[1] + 9.0 * s)]
    else:
        w = 4.3 if view == "back" else 5.0
        pts = [(neck[0] - w * 0.85 * s, top), (neck[0] + w * 0.85 * s, top), (pelvis[0] + (w + 0.9) * s + sway * 0.3, pelvis[1] + 9.2 * s),
               (pelvis[0] - (w + 0.9) * s + sway * 0.3, pelvis[1] + 9.2 * s)]
    poly(surf, col, pts, None)
    poly(surf, dk, [pts[0], ((pts[0][0] + pts[1][0]) / 2, top), ((pts[2][0] + pts[3][0]) / 2, pts[2][1]), pts[3]], None)
    trim(surf, pts, G[0], s, True, 0.42)
    if view == "back":
        c = ((pts[0][0] + pts[1][0]) / 2, top + 5.2 * s)
        pygame.draw.lines(surf, G[1], True, [I((p[0] + (c[0] - p[0]) * 0.12, p[1] + (c[1] - p[1]) * 0.08)) for p in pts], 1)
        if look["mat"] == "eclipse":
            eclipse_emblem(surf, c, 1.9 * s, t, col)
        else:
            dragon_emblem(surf, c, 1.6 * s, t, col)
        # hem runes
        for i in range(-2, 3):
            rune(surf, (c[0] + i * 1.7 * s, pts[2][1] - 1.3 * s), 1.4 * s, G[0], i)


# ---------------------------------------------------------------------------
def pauldron(surf, s, sh, look, sign, view, t):
    """Layered shaped pauldrons; size grows with tier; runes/gems/spikes on high tiers."""
    b, d, l = look["pal"]
    S = st(look)
    k = look["kind"]
    tier = look["tier"]
    if k in ("chainbody",):
        R = 1.75 * s
        poly(surf, b, [(sh[0] - R, sh[1] + 1.0 * s), (sh[0] - R * 0.7, sh[1] - R * 0.7), (sh[0] + R * 0.7, sh[1] - R * 0.75),
                       (sh[0] + R, sh[1] + 1.0 * s), (sh[0], sh[1] + 1.6 * s)])
        for yy in (-0.3, 0.5):
            for xx in (-0.9, 0, 0.9):
                surf.set_at(I((sh[0] + xx * s, sh[1] + yy * s)), l)
        return
    if k in ("leather_body", "goblin_mail"):
        R = 1.5 * s
        poly(surf, b, [(sh[0] - R, sh[1] + 0.9 * s), (sh[0] - R * 0.6, sh[1] - R * 0.7), (sh[0] + R * 0.6, sh[1] - R * 0.75), (sh[0] + R, sh[1] + 0.9 * s)])
        fl(surf, S["trim"], (sh[0] - R, sh[1] + 0.9 * s), (sh[0] + R, sh[1] + 0.9 * s), 1)
        dot(surf, S["rivet"], (sh[0], sh[1] - 0.1 * s), 0.3 * s)
        return
    # plate: 3 lames, bottom first
    R = (1.9 + 0.17 * tier) * s
    if tier >= 6:
        R = 2.75 * s
    # high tier ornaments behind the dome
    if look["mat"] == "mythos":
        for j, (ax, ay) in enumerate(((0.75, -1.35), (1.25, -0.95))):
            poly(surf, G[0], [(sh[0] + sign * R * 0.2, sh[1] - R * 0.55), (sh[0] + sign * R * ax, sh[1] - R * ay),
                              (sh[0] + sign * R * (ax - 0.05), sh[1] - R * (ay - 0.55)), (sh[0] + sign * R * 0.55, sh[1] - R * 0.3)], G[1])
    elif look["mat"] == "eclipse":
        for j in range(3):
            a = -math.pi / 2 + sign * (0.35 + 0.42 * j)
            p1 = (sh[0] + math.cos(a - 0.16) * R * 0.8, sh[1] - 0.2 * s + math.sin(a - 0.16) * R * 0.8)
            p2 = (sh[0] + math.cos(a) * R * 1.45, sh[1] - 0.2 * s + math.sin(a) * R * 1.3)
            p3 = (sh[0] + math.cos(a + 0.16) * R * 0.8, sh[1] - 0.2 * s + math.sin(a + 0.16) * R * 0.8)
            poly(surf, G[0], [p1, p2, p3], G[1])
    for j, (dy, f) in enumerate(((1.7, 0.78), (0.85, 0.9), (-0.15, 1.0))):
        r = R * f
        cy = sh[1] + dy * s
        lame = [(sh[0] - r, cy + 0.55 * s), (sh[0] - r * 0.92, cy - r * 0.42), (sh[0] - r * 0.5, cy - r * 0.78), (sh[0] + r * 0.5, cy - r * 0.8),
                (sh[0] + r * 0.92, cy - r * 0.42), (sh[0] + r, cy + 0.55 * s), (sh[0] + r * 0.4, cy + 0.9 * s), (sh[0] - r * 0.4, cy + 0.9 * s)]
        poly(surf, b if j != 1 else gear._mix(b, d) if hasattr(gear, "_mix") else b, lame)
        poly(surf, d, [lame[3], lame[4], lame[5], lame[6], (sh[0] + r * 0.1, cy + 0.9 * s), (sh[0] + r * 0.2, cy - r * 0.8)], None)
        trim(surf, lame[5:] + lame[:1], S["trim"], s, False, 0.45 if S["gold"] else 0.3)
    dome = (sh[0] - R * 0.35, sh[1] - R * 0.35)
    fl(surf, l, (sh[0] - R * 0.7, sh[1] - R * 0.25), (sh[0] - R * 0.1, sh[1] - R * 0.7), max(1, int(s * 0.35)))
    if S["gold"]:
        top = [(sh[0] - R, sh[1] + 0.4 * s), (sh[0] - R * 0.92, sh[1] - 0.15 * s - R * 0.42), (sh[0] - R * 0.5, sh[1] - 0.15 * s - R * 0.78),
               (sh[0] + R * 0.5, sh[1] - 0.15 * s - R * 0.8), (sh[0] + R * 0.92, sh[1] - 0.15 * s - R * 0.42), (sh[0] + R, sh[1] + 0.4 * s)]
        trim(surf, top, G[0], s, False, 0.45)
        gem(surf, (sh[0], sh[1] - 0.5 * s), 0.42 * s, S["gem"], t)
        rune(surf, (sh[0] - sign * R * 0.55, sh[1] + 1.2 * s), 1.3 * s, G[2], 1 if sign > 0 else 3)
    else:
        for i in range(S["rivets"] - 1):
            dot(surf, S["rivet"], (sh[0] - R * 0.6 + i * R * 1.2 / max(1, S["rivets"] - 2), sh[1] + 1.2 * s), 0.3 * s)


def arm_plate(surf, s, sh, el, hand, look, t):
    """Rerebrace, couter, vambrace and gauntlet over the arm joints."""
    b, d, l = look["pal"]
    S = st(look)
    from rs_humanoid_v2 import _limb, _circ
    _limb(surf, sh, el, 1.55 * s, 1.25 * s, b)
    _limb(surf, el, hand, 1.2 * s, 1.0 * s, b)
    # vambrace flare near the wrist
    dx, dy = hand[0] - el[0], hand[1] - el[1]
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    w0 = (hand[0] - ux * 1.2 * s, hand[1] - uy * 1.2 * s)
    cuff = [(w0[0] + nx * 1.35 * s, w0[1] + ny * 1.35 * s), (w0[0] - nx * 1.35 * s, w0[1] - ny * 1.35 * s),
            (w0[0] - nx * 1.0 * s - ux * 1.2 * s, w0[1] - ny * 1.0 * s - uy * 1.2 * s), (w0[0] + nx * 1.0 * s - ux * 1.2 * s, w0[1] + ny * 1.0 * s - uy * 1.2 * s)]
    poly(surf, d, cuff)
    fl(surf, S["trim"], cuff[0], cuff[1], max(1, int(s * 0.4)))
    _circ(surf, b, el, 1.05 * s)                     # couter
    dot(surf, S["trim"] if S["gold"] else l, el, 0.4 * s)
    # gauntlet
    _circ(surf, gear._shade(b, -12) if hasattr(gear, "_shade") else d, hand, 1.02 * s)
    fl(surf, l, (hand[0] - 0.5 * s, hand[1] - 0.4 * s), (hand[0] + 0.3 * s, hand[1] - 0.5 * s), 1)
    if S["gold"]:
        gem(surf, ((el[0] + hand[0]) / 2, (el[1] + hand[1]) / 2), 0.32 * s, S["gem"], None)


# ---------------------------------------------------------------------------
def leg_plate(surf, s, hip, knee, foot, look, view, facing, t):
    b, d, l = look["pal"]
    S = st(look)
    gold = S["gold"]
    from rs_humanoid_v2 import _limb, _circ
    _limb(surf, hip, knee, 1.95 * s, 1.45 * s, b)          # cuisse
    _limb(surf, knee, foot, 1.45 * s, 1.12 * s, b)         # greave
    # greave ridge
    fl(surf, l, (knee[0] - 0.35 * s, knee[1] + 1.2 * s), (foot[0] - 0.3 * s, foot[1] - 1.2 * s), max(1, int(s * 0.4)))
    if gold:
        fl(surf, G[0], (knee[0] + 0.9 * s, knee[1] + 1.0 * s), (foot[0] + 0.8 * s, foot[1] - 1.0 * s), 1)
        fl(surf, G[0], (knee[0] - 1.1 * s, knee[1] + 1.0 * s), (foot[0] - 0.9 * s, foot[1] - 1.0 * s), 1)
    # tasset on the upper thigh (follows the leg)
    dx, dy = knee[0] - hip[0], knee[1] - hip[1]
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    a = (hip[0] + ux * 0.4 * s, hip[1] + uy * 0.4 * s)
    bpt = (hip[0] + ux * L * 0.5, hip[1] + uy * L * 0.5)
    tw0, tw1 = 2.25 * s, 2.05 * s
    tas = [(a[0] + nx * tw0, a[1] + ny * tw0), (a[0] - nx * tw0, a[1] - ny * tw0), (bpt[0] - nx * tw1, bpt[1] - ny * tw1),
           (bpt[0] + ux * 0.5 * s, bpt[1] + uy * 0.5 * s), (bpt[0] + nx * tw1, bpt[1] + ny * tw1)]
    poly(surf, b, tas)
    mid = ((a[0] + bpt[0]) / 2, (a[1] + bpt[1]) / 2)
    fl(surf, d, (mid[0] + nx * tw0, mid[1] + ny * tw0), (mid[0] - nx * tw0, mid[1] - ny * tw0), 1)
    trim(surf, tas[2:] , S["trim"], s, False, 0.42 if gold else 0.3)
    if gold:
        rune(surf, (mid[0] + ux * 1.2 * s, mid[1] + uy * 1.2 * s), 1.3 * s, G[2], 0 if facing > 0 else 2)
    # knee cop with fan
    kc = G[0] if gold else b
    poly(surf, kc, [(knee[0] - 1.9 * s, knee[1] - 0.2 * s), (knee[0], knee[1] - 1.5 * s), (knee[0] + 1.9 * s, knee[1] - 0.2 * s), (knee[0], knee[1] + 1.2 * s)],
         G[1] if gold else OUT)
    _circ(surf, b if gold else l, knee, 1.0 * s, G[1] if gold else OUT)
    if gold:
        gem(surf, knee, 0.42 * s, S["gem"], t)
    else:
        dot(surf, S["rivet"], knee, 0.3 * s)
    # sabaton (replaces the boot)
    fx, fy = foot
    sab = gear._shade(b, -18) if hasattr(gear, "_shade") else d
    if view == "side":
        f = facing
        pts = [(fx - 1.2 * s * f, fy - 1.3 * s), (fx + 0.9 * s * f, fy - 1.3 * s), (fx + 1.3 * s * f, fy + 0.2 * s), (fx + 2.8 * s * f, fy + 0.9 * s),
               (fx + 2.8 * s * f, fy + 2.1 * s), (fx - 1.3 * s * f, fy + 2.1 * s)]
        poly(surf, sab, pts)
        for k in (0.2, 0.9):
            fl(surf, S["trim"], (fx + (0.4 + k) * s * f, fy - 0.2 * s + k * s), (fx + (0.6 + k) * s * f, fy + 2.0 * s), 1)
    else:
        pts = [(fx - 1.35 * s, fy - 1.3 * s), (fx + 1.35 * s, fy - 1.3 * s), (fx + 1.6 * s, fy + 2.1 * s), (fx - 1.6 * s, fy + 2.1 * s)]
        poly(surf, sab, pts)
        fl(surf, S["trim"], (fx - 1.4 * s, fy + 0.4 * s), (fx + 1.4 * s, fy + 0.4 * s), 1)
    if gold:
        fl(surf, G[0], pts[0], pts[1], 1)


def faulds(surf, s, pelvis, hw, top, look, view, t):
    """Two-row lame skirt below the belt (plate legs)."""
    b, d, l = look["pal"]
    S = st(look)
    for j in range(2):
        y0 = top + j * 1.35 * s
        w0, w1 = hw * (0.95 + 0.08 * j), hw * (1.05 + 0.08 * j)
        pts = [(pelvis[0] - w0, y0), (pelvis[0] + w0, y0), (pelvis[0] + w1, y0 + 1.6 * s), (pelvis[0] - w1, y0 + 1.6 * s)]
        poly(surf, b if j == 0 else gear._shade(b, -10) if hasattr(gear, "_shade") else b, pts)
        poly(surf, d, [(pelvis[0] + w0 * 0.1, y0), pts[1], pts[2], (pelvis[0] + w1 * 0.1, y0 + 1.6 * s)], None)
        fl(surf, S["trim"], pts[3], pts[2], max(1, int(s * (0.42 if S["gold"] else 0.3))))
        for i in range(S["rivets"]):
            u = (i + 0.5) / S["rivets"]
            dot(surf, S["rivet"], (pelvis[0] - w0 + 2 * w0 * u, y0 + 0.6 * s), 0.26 * s)
    if S["gold"] and view != "back":
        # hanging emblem tabard between the tassets
        col = (96, 18, 22) if look["mat"] == "mythos" else (30, 24, 42)
        tb = [(pelvis[0] - 1.4 * s, top + 0.2 * s), (pelvis[0] + 1.4 * s, top + 0.2 * s), (pelvis[0] + 1.2 * s, top + 5.6 * s),
              (pelvis[0], top + 6.4 * s), (pelvis[0] - 1.2 * s, top + 5.6 * s)]
        poly(surf, col, tb, None)
        trim(surf, tb, G[0], s, True, 0.4)
        rune(surf, (pelvis[0], top + 3.6 * s), 1.6 * s, G[2], 0 if look["mat"] == "mythos" else 1)
