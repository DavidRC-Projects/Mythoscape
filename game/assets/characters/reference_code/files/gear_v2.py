"""
gear_v2.py — per-item armour / weapon looks for the USE_NEW_CHARACTERS path.

Every equippable armour piece and weapon in server/content.py gets a LOOK:
  kind      silhouette family (sword, longsword, dagger, battleaxe, axe, pickaxe,
            cleaver, bow | platebody, chainbody, leather_body, goblin_mail |
            platelegs, chainlegs, chaps | med_helm, cowl, dragon_helm, grill_helm |
            kiteshield, sq_shield, round_wood, aegis)
  mat       material palette key (muted OSRS-like)
  tier      0..6, drives small detail (rivets, trims, guard shape, fuller)
Nothing here changes animation — drawers are handed positions/angles computed
by the unchanged rig code.
"""
import math
import pygame

# (base, dark, light) — muted, flat-shaded
MATS = {
    "bronze":  ((150, 108, 60), (104, 72, 38), (190, 146, 88)),
    "iron":    ((108, 106, 106), (72, 70, 72), (146, 144, 144)),
    "steel":   ((150, 152, 156), (100, 102, 108), (196, 198, 202)),
    "mithril": ((78, 88, 128), (50, 56, 88), (118, 130, 170)),
    "adamant": ((70, 104, 78), (44, 70, 50), (108, 144, 112)),
    "mythos":  ((146, 36, 34), (92, 18, 20), (196, 74, 60)),
    "eclipse": ((40, 38, 46), (20, 19, 24), (80, 78, 90)),
    "leather": ((116, 80, 48), (80, 54, 30), (150, 110, 70)),
    "goblin":  ((92, 98, 58), (60, 64, 36), (126, 130, 80)),
    "wood":    ((122, 86, 50), (84, 58, 32), (156, 116, 72)),
    "oak":     ((140, 104, 62), (98, 70, 40), (176, 138, 88)),
    "willow":  ((150, 138, 84), (106, 96, 56), (186, 174, 118)),
    "maple":   ((158, 96, 50), (112, 64, 32), (196, 132, 76)),
    "yew":     ((104, 62, 42), (70, 40, 26), (140, 90, 62)),
    "magic":   ((58, 96, 92), (36, 64, 62), (98, 150, 140)),
}
GOLD = ((196, 156, 64), (136, 102, 36), (232, 200, 110))
LEATHER_GRIP = ((86, 58, 36), (58, 38, 22), (118, 84, 54))
TIER = {"bronze": 1, "iron": 2, "steel": 3, "mithril": 4, "adamant": 5, "mythos": 6, "eclipse": 6}
OUT = (30, 24, 22)


def _mat_of(item_id):
    for m in ("mythos", "eclipse", "adamant", "mithril", "steel", "iron", "bronze"):
        if m in item_id:
            return m
    if item_id.startswith(("oak_", "willow_", "maple_", "yew_", "magic_")):
        return item_id.split("_")[0]
    if "leather" in item_id:
        return "leather"
    if "goblin" in item_id:
        return "goblin"
    if item_id in ("shortbow", "wooden_shield"):
        return "wood"
    return "iron"


def look_for(item_id):
    """Return the look dict for an item id (None if not armour/weapon)."""
    if not item_id:
        return None
    i = item_id
    mat = _mat_of(i)
    tier = TIER.get(mat, 1)
    if i == "eclipse_cleaver":
        kind = "cleaver"
    elif "longsword" in i:
        kind = "longsword"
    elif "dagger" in i:
        kind = "dagger"
    elif "battleaxe" in i:
        kind = "battleaxe"
    elif "pickaxe" in i:
        kind = "pickaxe"
    elif i.endswith("_axe"):
        kind = "axe"
    elif "sword" in i:
        kind = "sword"
    elif "bow" in i:
        kind = "bow"
    elif "chainbody" in i:
        kind = "chainbody"
    elif i == "leather_body":
        kind = "leather_body"
    elif i == "goblin_mail":
        kind = "goblin_mail"
    elif i.endswith("_body"):
        kind = "platebody"
    elif "chainlegs" in i:
        kind = "chainlegs"
    elif i == "leather_chaps":
        kind = "chaps"
    elif i.endswith("_legs"):
        kind = "platelegs"
    elif i == "leather_cowl":
        kind = "cowl"
    elif i == "mythos_helmet":
        kind = "dragon_helm"
    elif i == "eclipse_helmet":
        kind = "grill_helm"
    elif i.endswith("_helmet"):
        kind = "med_helm"
    elif i == "wooden_shield":
        kind = "round_wood"
    elif i == "eclipse_shield":
        kind = "aegis"
    elif "sq_shield" in i:
        kind = "sq_shield"
    elif i.endswith("_shield"):
        kind = "kiteshield"
    else:
        return None
    return {"kind": kind, "mat": mat, "tier": tier, "pal": MATS.get(mat, MATS["iron"]),
            "gold": mat in ("mythos", "eclipse")}


# ---------------------------------------------------------------------------
# Flat-shaded helpers
def fpoly(surf, col, pts, outline=OUT, w=1):
    ip = [(int(round(x)), int(round(y))) for x, y in pts]
    if len(ip) < 3:
        return
    pygame.draw.polygon(surf, col, ip)
    if outline:
        pygame.draw.polygon(surf, outline, ip, w)


def fline(surf, col, a, b, w=1):
    pygame.draw.line(surf, col, (int(round(a[0])), int(round(a[1]))), (int(round(b[0])), int(round(b[1]))), max(1, int(w)))


# ---------------------------------------------------------------------------
# Weapons — local coordinates: grip at (0,0), business end toward -y.
# R(px,py) maps local -> screen (supplied by the caller: unchanged transform).
def draw_weapon_shape(surf, R, look, draw_amt=0.0, s=3.0):
    _draw_weapon_shape_base(surf, R, look, draw_amt, s)
    if look["mat"] in ("mythos", "eclipse"):
        import armour_v2 as A
        k = look["kind"]
        L = {"dagger": 7.4, "sword": 12.6, "longsword": 15.6, "cleaver": 15.0}.get(k, 12.0)
        # gold runes down the blade + glowing gem in the guard / pommel
        for i in range(3 if k != "dagger" else 1):
            y = -3.2 - i * (L - 5.0) / 3.0
            A.rune(surf, R(0.0 if k != "cleaver" else 1.8, y), max(3, 1.1 * s), A.G[2], i)
        gc = (230, 30, 36) if look["mat"] == "mythos" else (255, 176, 60)
        A.gem(surf, R(0, 2.9), max(1, s * 0.45), gc, 0.0)
        if k == "cleaver":
            A.gem(surf, R(1.3, -6.0), max(1, s * 0.5), gc, 0.0)


def _draw_weapon_shape_base(surf, R, look, draw_amt=0.0, s=3.0):
    kind, (b, d, l), tier = look["kind"], look["pal"], look["tier"]
    g = GOLD
    wood = MATS["wood"]
    lw = max(1, int(s * 0.35))
    if kind in ("sword", "longsword", "dagger"):
        L = {"dagger": 7.4, "sword": 12.6, "longsword": 15.6}[kind]
        hw = {"dagger": 0.85, "sword": 1.0, "longsword": 1.1}[kind]
        if look["mat"] == "mythos":
            hw *= 1.1
        # grip + pommel
        fpoly(surf, LEATHER_GRIP[0], [R(-0.45, 2.4), R(0.45, 2.4), R(0.45, -0.8), R(-0.45, -0.8)])
        pc = g if look["gold"] or tier >= 4 else (b, d, l)
        fpoly(surf, pc[0], [R(-0.8, 2.3), R(0.8, 2.3), R(0.6, 3.3), R(-0.6, 3.3)])
        # blade (two facets: light left half, dark right half)
        tipy = -L
        base_y = -1.3
        fpoly(surf, l, [R(-hw, base_y), R(0, base_y), R(0, tipy), R(-hw, tipy + 2.0 * hw)], None)
        fpoly(surf, b, [R(0, base_y), R(hw, base_y), R(hw, tipy + 2.0 * hw), R(0, tipy)], None)
        fpoly(surf, b, [R(-hw, base_y), R(hw, base_y), R(hw, tipy + 2.0 * hw), R(0, tipy), R(-hw, tipy + 2.0 * hw)], OUT, 1) if False else None
        pygame.draw.lines(surf, OUT, True, [tuple(map(int, R(*p))) for p in
                          ((-hw, base_y), (hw, base_y), (hw, tipy + 2.0 * hw), (0, tipy), (-hw, tipy + 2.0 * hw))], 1)
        if kind == "longsword" or tier >= 3:
            fline(surf, d, R(0, base_y - 0.6), R(0, tipy + 3.0), max(1, s * 0.22))  # fuller
        # crossguard — shape by tier
        gc = g if (look["gold"] or tier >= 5) else (b, d, l)
        if tier <= 1:      # bronze: plain straight bar
            fpoly(surf, gc[1], [R(-1.9, -0.6), R(1.9, -0.6), R(1.9, -1.4), R(-1.9, -1.4)])
        elif tier == 2:    # iron: bar with square ends
            fpoly(surf, gc[1], [R(-2.1, -0.5), R(2.1, -0.5), R(2.1, -1.5), R(-2.1, -1.5)])
            fpoly(surf, gc[0], [R(-2.5, -0.3), R(-1.7, -0.3), R(-1.7, -1.7), R(-2.5, -1.7)])
            fpoly(surf, gc[0], [R(1.7, -0.3), R(2.5, -0.3), R(2.5, -1.7), R(1.7, -1.7)])
        elif tier == 3:    # steel: angled-down quillons
            fpoly(surf, gc[1], [R(-2.6, 0.3), R(0, -0.7), R(2.6, 0.3), R(2.6, -0.5), R(0, -1.5), R(-2.6, -0.5)])
        elif tier == 4:    # mithril: upswept quillons
            fpoly(surf, gc[0], [R(-2.6, -2.2), R(0, -0.6), R(2.6, -2.2), R(2.6, -1.3), R(0, 0.3), R(-2.6, -1.3)])
        elif tier == 5:    # adamant: winged guard
            fpoly(surf, gc[0], [R(-3.0, -1.8), R(-1.0, -0.4), R(1.0, -0.4), R(3.0, -1.8), R(1.2, -1.6), R(0, -1.3), R(-1.2, -1.6)])
        else:              # mythos: dragon-wing gold guard + ruby
            fpoly(surf, g[0], [R(-3.4, -2.6), R(-1.2, -0.4), R(1.2, -0.4), R(3.4, -2.6), R(1.4, -1.8), R(0, -1.4), R(-1.4, -1.8)])
            pygame.draw.circle(surf, (170, 30, 40), tuple(map(int, R(0, -0.8))), max(1, int(s * 0.4)))
    elif kind in ("battleaxe", "axe", "pickaxe"):
        top = {"battleaxe": -14.5, "axe": -11.0, "pickaxe": -11.0}[kind]
        fpoly(surf, wood[0], [R(-0.45, 2.6), R(0.45, 2.6), R(0.45, top), R(-0.45, top)])
        fline(surf, wood[2], R(-0.2, 2.2), R(-0.2, top + 0.5), 1)
        hy = top + 1.6
        if kind == "battleaxe":
            # double-bit crescent head; tier widens the bits
            wbit = 3.6 + 0.35 * tier
            for sgn in (1, -1):
                fpoly(surf, b, [R(0.3 * sgn, hy - 1.4), R(wbit * sgn, hy - 3.4), R((wbit + 0.6) * sgn, hy + 0.6),
                                R(wbit * sgn, hy + 3.6), R(0.3 * sgn, hy + 1.8)])
                fline(surf, l, R((wbit + 0.2) * sgn, hy - 2.6), R((wbit + 0.5) * sgn, hy + 2.8), max(1, s * 0.3))
            if tier >= 3:
                fpoly(surf, d, [R(-0.9, hy - 1.8), R(0.9, hy - 1.8), R(0.9, hy + 2.2), R(-0.9, hy + 2.2)])
            if tier >= 4:
                fpoly(surf, b, [R(-0.5, top - 0.2), R(0.5, top - 0.2), R(0, top - 2.6)])  # top spike
        elif kind == "axe":
            fpoly(surf, b, [R(0.3, hy - 1.0), R(3.9, hy - 2.4), R(4.4, hy + 0.6), R(3.9, hy + 2.8), R(0.3, hy + 1.4)])
            fline(surf, l, R(4.0, hy - 1.8), R(4.3, hy + 2.2), max(1, s * 0.3))
            fpoly(surf, d, [R(-0.3, hy - 0.8), R(-1.6, hy - 0.4), R(-1.6, hy + 0.9), R(-0.3, hy + 1.2)])
        else:  # pickaxe
            fpoly(surf, b, [R(-5.0, hy + 1.6), R(-1.0, hy - 1.0), R(1.0, hy - 1.0), R(5.0, hy + 1.6), R(1.0, hy + 0.3), R(-1.0, hy + 0.3)])
            fline(surf, l, R(-4.4, hy + 1.0), R(4.4, hy + 1.0), 1)
    elif kind == "cleaver":
        # Eclipse Cleaver: broad obsidian slab with a gold edge and eclipse disc
        fpoly(surf, LEATHER_GRIP[1], [R(-0.5, 3.0), R(0.5, 3.0), R(0.5, -1.0), R(-0.5, -1.0)])
        fpoly(surf, g[0], [R(-2.2, -0.6), R(2.2, -0.6), R(2.2, -1.6), R(-2.2, -1.6)])
        blade = [R(-1.2, -1.6), R(3.2, -1.6), R(4.4, -9.0), R(4.0, -15.2), R(0.4, -15.6), R(-1.2, -12.0)]
        fpoly(surf, b, blade)
        fpoly(surf, d, [R(1.6, -1.6), R(3.2, -1.6), R(4.4, -9.0), R(4.0, -15.2), R(2.4, -15.3)], None)
        fline(surf, g[0], R(3.3, -1.8), R(4.5, -9.0), max(1, s * 0.4))
        fline(surf, g[0], R(4.5, -9.0), R(4.1, -15.0), max(1, s * 0.4))
        c = R(1.3, -6.0)
        pygame.draw.circle(surf, g[0], (int(c[0]), int(c[1])), max(2, int(s * 0.95)))
        pygame.draw.circle(surf, b, (int(c[0] + s * 0.3), int(c[1])), max(1, int(s * 0.75)))
    elif kind == "bow":
        # D-profile shortbow, limbs bend toward +x; string pulled by draw_amt
        L = 9.0
        pts = []
        for k in range(9):
            u = -1 + 2 * k / 8.0
            pts.append((2.6 * (1 - u * u) - 0.4 * abs(u) ** 3, u * L))
        for a, c2 in zip(pts, pts[1:]):
            fline(surf, OUT, R(*a), R(*c2), max(2, s * 0.85))
        for a, c2 in zip(pts, pts[1:]):
            fline(surf, b, R(*a), R(*c2), max(1, s * 0.5))
        fpoly(surf, LEATHER_GRIP[0], [R(2.0, -1.3), R(3.0, -1.3), R(3.0, 1.3), R(2.0, 1.3)])
        nock = -2.2 * max(0.0, min(1.2, draw_amt))
        str_col = (226, 220, 200) if look["mat"] != "magic" else (170, 240, 220)
        fline(surf, str_col, R(pts[0][0], -L), R(nock, 0), 1)
        fline(surf, str_col, R(nock, 0), R(pts[-1][0], L), 1)
        if draw_amt > 0.05:  # nocked arrow while drawing (same cue as the old drawer)
            fline(surf, (150, 112, 70), R(nock, 0), R(5.2, 0), max(1, s * 0.3))
            fpoly(surf, (170, 170, 176), [R(5.2, -0.6), R(6.6, 0), R(5.2, 0.6)], None)
        if look["mat"] == "magic":
            for yy in (-6, 6):
                pygame.draw.circle(surf, (120, 220, 200), tuple(map(int, R(1.2, yy))), max(1, int(s * 0.35)))
        elif look["mat"] in ("yew", "maple"):
            fline(surf, look["pal"][2], R(1.8, -5), R(1.8, -3), 1)
            fline(surf, look["pal"][2], R(1.8, 3), R(1.8, 5), 1)


def weapon_transform(hx, hy, s, kind, facing, swing, sheathed=False):
    """
    EXACT copy of the placement/angle maths in rs_humanoid._draw_weapon
    (so attack swings, sheathe and bow draw sit on the same path as before).
    Returns (R, combat).
    """
    if sheathed:
        combat = 0.0
        if kind in ("battleaxe", "axe", "pickaxe", "staff"):
            rest = -0.12
        elif kind == "bow":
            rest = -0.20
        else:
            rest = -0.08
        ang = rest * facing
        ws = s * 1.08
    else:
        combat = max(0.0, min(1.0, abs(float(swing or 0.0)) / 0.55))
        if kind == "bow":
            combat = max(0.0, min(1.2, abs(float(swing or 0.0))))
            ang = -0.12 * facing
            ws = s * 1.05
            hx = hx + 0.6 * s * facing
            hy = hy - 0.4 * s
        else:
            if kind in ("battleaxe", "axe", "pickaxe"):
                rest = -0.18 + 0.06 * (1.0 - combat)
            else:
                rest = 2.05 * (1.0 - combat) + (-0.52) * combat
            ang = (rest + float(swing or 0.0) * 1.05) * facing
            ws = s * 1.02
            side = 0.45 * s if kind in ("battleaxe", "axe", "pickaxe") else 1.55 * s
            hx = hx + (side * facing) * (1.0 - combat) + (0.85 * s * facing) * combat * max(0.0, float(swing or 0.0))
            hy = hy + (0.35 * s) * (1.0 - combat) - (0.35 * s) * combat * max(0.0, float(swing or 0.0))
    c, sn = math.cos(ang), math.sin(ang)

    def R(px, py):
        x = px * ws
        y = py * ws
        if sheathed:
            x = -x
            y = y + 16.5 * ws
        return hx + (x * c - y * sn) * facing, hy + (x * sn + y * c)
    return R, combat


def old_kind(look_kind):
    """Map v2 kinds to the old _weapon_kind families used by the transform."""
    return {"longsword": "sword", "dagger": "dagger", "cleaver": "battleaxe"}.get(look_kind, look_kind)


def draw_weapon(surf, hx, hy, s, item_id, facing, swing, sheathed=False, fallback_kind=None):
    look = look_for(item_id) if item_id else None
    if look is None or look["kind"] not in ("sword", "longsword", "dagger", "battleaxe", "axe", "pickaxe", "cleaver", "bow"):
        # generic props (fishing rod etc.) — let the caller use the old drawer
        return False
    # old transform keys off weapon_style(): dagger/sword/battleaxe/axe/pickaxe/bow
    tkind = fallback_kind or old_kind(look["kind"])
    R, combat = weapon_transform(hx, hy, s, tkind, facing, swing, sheathed)
    draw_weapon_shape(surf, R, look, draw_amt=combat if look["kind"] == "bow" else 0.0, s=s)
    return True


# ---------------------------------------------------------------------------
# Shields — (cx, cy) centre, sc = size unit. `facing` flips the boss light.
def draw_shield(surf, cx, cy, sc, item_id, on_back=False):
    look = look_for(item_id or "wooden_shield")
    b, d, l = look["pal"]
    k = look["kind"]
    P = lambda x, y: (cx + x * sc, cy + y * sc)
    if item_id in ("mythos_shield", "eclipse_shield"):
        return _draw_royal_shield(surf, cx, cy, sc, item_id, look)
    if look["tier"] >= 2 and k in ("kiteshield", "sq_shield"):
        pass
    if k == "round_wood":
        pygame.draw.circle(surf, OUT, (int(cx), int(cy)), int(3.9 * sc))
        pygame.draw.circle(surf, MATS["iron"][0], (int(cx), int(cy)), int(3.9 * sc) - 1)
        pygame.draw.circle(surf, b, (int(cx), int(cy)), int(3.2 * sc))
        for x in (-1.6, 0, 1.6):
            fline(surf, d, P(x, -3.0), P(x, 3.0), 1)
        pygame.draw.circle(surf, MATS["iron"][2], (int(cx), int(cy)), max(1, int(0.9 * sc)))
    elif k == "sq_shield":
        fpoly(surf, b, [P(-3.2, -3.8), P(3.2, -3.8), P(3.2, 3.4), P(-3.2, 3.4)])
        fpoly(surf, d, [P(0, -3.8), P(3.2, -3.8), P(3.2, 3.4), P(0, 3.4)], None)
        fline(surf, l, P(-3.0, -3.6), P(3.0, -3.6), 1)
        for x, y in ((-2.4, -3.0), (2.4, -3.0), (-2.4, 2.6), (2.4, 2.6)):
            pygame.draw.circle(surf, l, (int(P(x, y)[0]), int(P(x, y)[1])), max(1, int(0.35 * sc)))
        pygame.draw.circle(surf, l, (int(cx), int(cy - 0.2 * sc)), max(1, int(0.9 * sc)))
        pygame.draw.rect(surf, OUT, pygame.Rect(int(cx - 3.2 * sc), int(cy - 3.8 * sc), int(6.4 * sc) + 1, int(7.2 * sc) + 1), 1)
    elif k in ("kiteshield",):
        pts = [P(-3.4, -4.2), P(3.4, -4.2), P(3.2, 0.2), P(0, 5.4), P(-3.2, 0.2)]
        fpoly(surf, b, pts)
        fpoly(surf, d, [P(0, -4.2), P(3.4, -4.2), P(3.2, 0.2), P(0, 5.4)], None)
        # tier-coloured cross stripe
        stripe = GOLD[1] if look["tier"] >= 5 else l
        fline(surf, stripe, P(0, -4.0), P(0, 5.0), max(1, sc * 0.45))
        if look["tier"] >= 3:
            fline(surf, stripe, P(-3.2, -1.6), P(3.2, -1.6), max(1, sc * 0.35))
        pygame.draw.polygon(surf, OUT, [tuple(map(int, p)) for p in pts], 1)
    elif k == "aegis" or (k == "kiteshield" and look["mat"] == "mythos"):
        pass
    if item_id == "mythos_shield":
        pts = [P(-3.6, -4.4), P(3.6, -4.4), P(3.4, 0.4), P(0, 5.8), P(-3.4, 0.4)]
        fpoly(surf, b, pts)
        fpoly(surf, d, [P(0, -4.4), P(3.6, -4.4), P(3.4, 0.4), P(0, 5.8)], None)
        pygame.draw.polygon(surf, GOLD[0], [tuple(map(int, p)) for p in pts], max(1, int(sc * 0.45)))
        # gold dragon-head chevron
        fpoly(surf, GOLD[0], [P(-1.6, -2.0), P(0, -0.6), P(1.6, -2.0), P(1.0, 0.8), P(0, 2.2), P(-1.0, 0.8)], GOLD[1])
    elif k == "aegis":
        pygame.draw.circle(surf, OUT, (int(cx), int(cy)), int(4.2 * sc))
        pygame.draw.circle(surf, GOLD[0], (int(cx), int(cy)), int(4.2 * sc) - 1)
        pygame.draw.circle(surf, b, (int(cx), int(cy)), int(3.5 * sc))
        pygame.draw.circle(surf, GOLD[0], (int(cx), int(cy)), int(1.8 * sc))
        pygame.draw.circle(surf, b, (int(cx + 0.7 * sc), int(cy - 0.3 * sc)), int(1.5 * sc))
        for a in range(8):
            ang = a * math.pi / 4
            fline(surf, GOLD[1], (cx + math.cos(ang) * 2.3 * sc, cy + math.sin(ang) * 2.3 * sc),
                  (cx + math.cos(ang) * 3.2 * sc, cy + math.sin(ang) * 3.2 * sc), 1)


# ---------------------------------------------------------------------------
# Inventory / equipment icons
def draw_icon(surf, rect, item_id, items_db=None):
    """Draw an item icon in rect. Returns False if not handled (caller falls back)."""
    items_db = items_db or {}
    item = items_db.get(item_id) or {}
    cx, cy = rect.center
    look = look_for(item_id)
    slot = item.get("equip_slot")
    sz = min(rect.w, rect.h)
    if look is not None:
        k = look["kind"]
        if k in ("sword", "longsword", "dagger", "battleaxe", "axe", "pickaxe", "cleaver", "bow"):
            L = {"dagger": 11.5, "sword": 16.5, "longsword": 19.5, "battleaxe": 18, "axe": 14.5,
                 "pickaxe": 14.5, "cleaver": 19.5, "bow": 19}[k]
            ws = sz / (L * 1.25)
            ang = 0.0 if k == "bow" else math.pi / 4
            c, sn = math.cos(ang), math.sin(ang)
            oy = (L * 0.5 - 3.0) if k != "bow" else 0.0

            def R(px, py):
                py = py + oy
                return cx + (px * c - py * sn) * ws, cy + (px * sn + py * c) * ws
            draw_weapon_shape(surf, R, look, 0.0, ws)
            return True
        b, d, l = look["pal"]
        u = sz / 16.0
        P = lambda x, y: (cx + x * u, cy + y * u)
        gold = look["gold"]
        if k in ("platebody", "chainbody", "leather_body", "goblin_mail"):
            body = [P(-3.6, -5.6), P(-1.4, -6.2), P(0, -4.8), P(1.4, -6.2), P(3.6, -5.6), P(6.4, -4.0), P(6.6, 1.0),
                    P(4.2, 1.2), P(3.6, -1.0), P(3.8, 6.0), P(-3.8, 6.0), P(-3.6, -1.0), P(-4.2, 1.2), P(-6.6, 1.0), P(-6.4, -4.0)]
            fpoly(surf, b, body)
            fpoly(surf, d, [P(0, -4.8), P(1.4, -6.2), P(3.6, -5.6), P(3.8, 6.0), P(0, 6.0)], None)
            if k == "chainbody":
                for yy in range(-4, 6, 2):
                    for xx in range(-3, 4, 2):
                        pygame.draw.circle(surf, l, (int(P(xx + (yy % 4) * 0.25, yy)[0]), int(P(0, yy)[1])), max(1, int(u * 0.45)), 1)
            elif k == "platebody":
                fline(surf, l, P(0, -4.4), P(0, 5.4), max(1, u * 0.6))
                fpoly(surf, l if not gold else GOLD[0], [P(-6.4, -4.0), P(-3.6, -5.6), P(-3.2, -2.6), P(-6.5, -1.6)])
                fpoly(surf, d if not gold else GOLD[1], [P(6.4, -4.0), P(3.6, -5.6), P(3.2, -2.6), P(6.5, -1.6)])
                if gold:
                    fline(surf, GOLD[0], P(-3.8, 5.4), P(3.8, 5.4), max(1, u * 0.8))
                    pygame.draw.circle(surf, GOLD[0], (int(cx), int(P(0, -1.0)[1])), max(2, int(u * 1.5)))
                    if look["mat"] == "eclipse":
                        pygame.draw.circle(surf, b, (int(cx + u * 0.6), int(P(0, -1.0)[1])), max(1, int(u * 1.2)))
                if look["tier"] >= 4:
                    fline(surf, l, P(-3.6, 2.0), P(3.6, 2.0), 1)
            elif k == "leather_body":
                fline(surf, l, P(-2.4, -3.6), P(-2.4, 5.0), 1)
                fline(surf, l, P(2.4, -3.6), P(2.4, 5.0), 1)
                fline(surf, LEATHER_GRIP[1], P(-3.8, 3.0), P(3.8, 3.0), max(1, u))
            else:  # goblin mail: rusty patches + rivets
                fpoly(surf, (116, 84, 50), [P(-3.0, -2.0), P(0.4, -2.4), P(0.6, 1.4), P(-2.8, 1.8)])
                for xx, yy in ((-2, -3), (2, 0), (-1, 4), (3, 4)):
                    pygame.draw.circle(surf, l, (int(P(xx, yy)[0]), int(P(xx, yy)[1])), max(1, int(u * 0.5)))
            return True
        if k in ("platelegs", "chainlegs", "chaps"):
            legs = [P(-4.2, -6.0), P(4.2, -6.0), P(4.8, 6.4), P(1.2, 6.4), P(0, -1.4), P(-1.2, 6.4), P(-4.8, 6.4)]
            fpoly(surf, b, legs)
            fpoly(surf, d, [P(0, -6.0), P(4.2, -6.0), P(4.8, 6.4), P(1.2, 6.4), P(0, -1.4)], None)
            fline(surf, GOLD[0] if gold else l, P(-4.2, -5.0), P(4.2, -5.0), max(1, u * 0.8))
            if k == "platelegs":
                for xx in (-3.0, 3.0):
                    pygame.draw.circle(surf, GOLD[0] if gold else l, (int(P(xx, 1.6)[0]), int(P(xx, 1.6)[1])), max(1, int(u * 1.1)))
            elif k == "chainlegs":
                for yy in range(-3, 6, 2):
                    for xx in (-3.2, -1.8, 1.8, 3.2):
                        pygame.draw.circle(surf, l, (int(P(xx, yy)[0]), int(P(xx, yy)[1])), max(1, int(u * 0.4)), 1)
            else:
                fpoly(surf, l, [P(-3.8, -3.8), P(-1.6, -3.8), P(-1.6, 4.0), P(-4.0, 4.0)], None)
            return True
        if k in ("med_helm", "cowl", "dragon_helm", "grill_helm"):
            # draw via the head drawer at icon scale
            draw_helmet_front(surf, cx, cy + u * 1.4, u * 1.35, item_id)
            return True
        if k in ("kiteshield", "sq_shield", "round_wood", "aegis"):
            draw_shield(surf, cx, cy, u * 1.55, item_id)
            return True
    if slot == "ammo":
        if item_id == "arrow_quiver":
            u = sz / 16.0
            fpoly(surf, MATS["leather"][0], [(cx - 3 * u, cy - 4 * u), (cx + 3 * u, cy - 4 * u), (cx + 2.4 * u, cy + 6 * u), (cx - 2.4 * u, cy + 6 * u)])
            for xx in (-1.6, 0, 1.6):
                fline(surf, (200, 190, 170), (cx + xx * u, cy - 4 * u), (cx + xx * u, cy - 7 * u), 1)
            return True
        u = sz / 16.0
        tip = MATS.get(_mat_of(item_id), MATS["iron"])
        for off in (-2.4, 0, 2.4):
            a = (cx - 5 * u + off * u, cy + 5 * u)
            bpt = (cx + 5 * u + off * u, cy - 5 * u)
            fline(surf, (150, 112, 70), a, bpt, max(1, u * 0.6))
            fpoly(surf, tip[0], [bpt, (bpt[0] - 2.2 * u, bpt[1] + 0.6 * u), (bpt[0] - 0.6 * u, bpt[1] + 2.2 * u)], OUT)
            fpoly(surf, (220, 220, 210), [a, (a[0] + 1.6 * u, a[1] - 0.2 * u), (a[0] + 0.2 * u, a[1] - 1.6 * u)], None)
        return True
    if slot in ("amulet", "ring"):
        gem = tuple(item.get("gem_color") or (200, 180, 90))
        u = sz / 16.0
        metal = GOLD[0] if "bronze" not in item_id else MATS["bronze"][0]
        if slot == "ring":
            pygame.draw.circle(surf, OUT, (int(cx), int(cy + u)), int(4.2 * u), max(2, int(u * 1.6)))
            pygame.draw.circle(surf, metal, (int(cx), int(cy + u)), int(4.0 * u), max(1, int(u * 1.1)))
            pygame.draw.circle(surf, OUT, (int(cx), int(cy - 3.2 * u)), max(2, int(1.8 * u)))
            pygame.draw.circle(surf, gem, (int(cx), int(cy - 3.2 * u)), max(1, int(1.5 * u)))
        else:
            pygame.draw.arc(surf, metal, pygame.Rect(int(cx - 5 * u), int(cy - 7 * u), int(10 * u), int(10 * u)), math.pi * 1.05, math.pi * 1.95, max(1, int(u * 0.8)))
            pygame.draw.lines(surf, metal, False, [(cx - 5 * u, cy - 2 * u), (cx, cy + 2.6 * u), (cx + 5 * u, cy - 2 * u)], max(1, int(u * 0.8)))
            pygame.draw.circle(surf, OUT, (int(cx), int(cy + 3.6 * u)), max(2, int(2.4 * u)))
            pygame.draw.circle(surf, metal, (int(cx), int(cy + 3.6 * u)), max(2, int(2.1 * u)))
            pygame.draw.circle(surf, gem, (int(cx), int(cy + 3.6 * u)), max(1, int(1.5 * u)))
        return True
    return False


# ---------------------------------------------------------------------------
# Helmets (front / side / back) — (hx, hy) = head centre, u = head unit
def _draw_helmet_front_v1(surf, hx, hy, u, item_id, view="front", facing=1):
    look = look_for(item_id)
    if look is None:
        return
    b, d, l = look["pal"]
    k = look["kind"]
    P = lambda x, y: (hx + x * u * (facing if view == "side" else 1), hy + y * u)
    side = view == "side"
    back = view == "back"
    if k == "cowl":
        pts = [P(-2.7, 2.6), P(-2.8, -1.2), P(-1.8, -3.1), P(0, -3.6), P(1.8, -3.1), P(2.8, -1.2), P(2.7, 2.6), P(1.6, 3.4), P(-1.6, 3.4)]
        if side:
            pts = [P(-2.8, 2.8), P(-2.8, -1.2), P(-1.6, -3.2), P(0.4, -3.6), P(2.0, -2.8), P(2.6, -1.4), P(1.2, -1.6), P(0.4, 0.6), P(0.8, 2.8), P(-0.6, 3.6)]
        fpoly(surf, b, pts)
        if not back and not side:
            fpoly(surf, d, [P(-1.9, -1.4), P(1.9, -1.4), P(1.9, 2.2), P(0, 2.9), P(-1.9, 2.2)], None)  # face opening shadow
        fline(surf, l, P(-2.0, -2.6), P(1.0, -3.2), 1)
        return
    if k == "med_helm":
        t = look["tier"]
        dome = [P(-2.6, -0.4), P(-2.4, -2.2), P(-1.4, -3.3), P(0, -3.6), P(1.4, -3.3), P(2.4, -2.2), P(2.6, -0.4)]
        if t == 5:  # adamant: taller comb crest
            dome = dome[:3] + [P(-0.4, -4.4), P(0.4, -4.4)] + dome[4:]
        fpoly(surf, b, dome + [P(2.6, 0.2), P(-2.6, 0.2)])
        fpoly(surf, d, [P(0, -3.6), P(1.4, -3.3), P(2.4, -2.2), P(2.6, -0.4), P(2.6, 0.2), P(0, 0.2)], None) if not side else None
        fpoly(surf, l, [P(-2.0, -2.0), P(-1.2, -3.0), P(-0.4, -3.2), P(-1.4, -1.6)], None)
        fline(surf, d, P(-2.6, -0.1), P(2.6, -0.1), max(1, u * 0.45))  # brow band
        if t >= 2 and not back:   # iron+: nasal guard
            nx = 1.3 if side else 0.0
            fpoly(surf, b, [P(nx - 0.35, 0.0), P(nx + 0.35, 0.0), P(nx + 0.3, 1.6), P(nx - 0.3, 1.6)])
        if t >= 3:                 # steel+: cheek guards
            for sx in ((-2.6,) if side else (-2.6, 2.2)):
                fpoly(surf, b, [P(sx, 0.2), P(sx + 0.5, 0.2), P(sx + 0.5, 2.0), P(sx, 1.6)])
        if t == 4:                 # mithril: centre ridge
            fline(surf, l, P(0, -3.5), P(0, -0.3), max(1, u * 0.35))
        if t == 2:                 # iron: rivets on the band
            for xx in (-1.8, -0.6, 0.6, 1.8):
                pygame.draw.circle(surf, l, (int(P(xx, -0.1)[0]), int(P(xx, -0.1)[1])), max(1, int(u * 0.22)))
        return
    if k == "dragon_helm":
        g = GOLD
        full = [P(-2.8, 2.4), P(-2.9, -1.2), P(-2.0, -3.2), P(0, -3.8), P(2.0, -3.2), P(2.9, -1.2), P(2.8, 2.4), P(1.2, 3.4), P(-1.2, 3.4)]
        # horns / fins
        for sg in (-1, 1):
            if side and sg > 0:
                continue
            fpoly(surf, g[0], [P(2.2 * sg, -2.4), P(4.4 * sg, -5.2), P(3.6 * sg, -2.0), P(2.8 * sg, -1.0)], g[1])
        fpoly(surf, b, full)
        if not back:
            fpoly(surf, (24, 12, 14), [P(-1.9, -0.6), P(1.9, -0.6), P(1.2, 0.2), P(-1.2, 0.2)], None)   # visor slit
            fpoly(surf, g[0], [P(-0.35, -3.6), P(0.35, -3.6), P(0.3, 2.8), P(-0.3, 2.8)], None)
        fline(surf, g[0], P(-2.8, 2.2), P(2.8, 2.2), max(1, u * 0.4))
        return
    if k == "grill_helm":
        g = GOLD
        full = [P(-2.8, 2.6), P(-2.9, -1.2), P(-2.0, -3.2), P(0, -3.7), P(2.0, -3.2), P(2.9, -1.2), P(2.8, 2.6), P(1.2, 3.4), P(-1.2, 3.4)]
        fpoly(surf, b, full)
        if not back:
            x0, x1 = (-0.4, 2.4) if side else (-1.8, 1.8)
            fpoly(surf, (14, 12, 16), [P(x0, -1.0), P(x1, -1.0), P(x1, 2.0), P(x0, 2.0)], None)
            n = 3 if side else 4
            for i in range(n):
                xx = x0 + (x1 - x0) * (i + 0.5) / n
                fline(surf, g[0], P(xx, -1.0), P(xx, 2.0), max(1, u * 0.3))
            fline(surf, g[0], P(x0, -1.0), P(x1, -1.0), max(1, u * 0.35))
        fline(surf, g[0], P(0, -3.6), P(0, -1.2), max(1, u * 0.35))
        fline(surf, g[0], P(-2.8, 2.4), P(2.8, 2.4), max(1, u * 0.35))
        return


def _shade(c, d):
    return tuple(max(0, min(255, v + d)) for v in c)


def _mix(a, b, k=0.5):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Heavier helms (bulk pass). Everything stays at y >= HELM_TOP (in head units)
# so crests / horns / wings stay under the HP bar (checked by tools/anchor_check).
HELM_TOP = -4.25


def draw_helmet_front(surf, hx, hy, u, item_id, view="front", facing=1, t=0.0):
    import armour_v2 as A
    look = look_for(item_id)
    if look is None:
        return
    b, d, l = look["pal"]
    k, tier, mat = look["kind"], look["tier"], look["mat"]
    side, back = view == "side", view == "back"
    f = facing if side else 1

    def P(x, y):
        # squash everything above the brow so the tallest crest/horn (-4.25)
        # lands at -3.6 head units -> stays at/under the HP bar (tools/anchor_check.py)
        y = max(HELM_TOP, y)
        if y < -1.5:
            y = -1.5 + (y + 1.5) * 0.72
        return (hx + x * u * f, hy + y * u)
    S = A.STYLE.get(mat, A.STYLE["iron"])
    trimc = S["trim"]
    Gd = A.G

    def body(pts, col=b, dark=d):
        fpoly(surf, col, [P(*q) for q in pts])
        if not side:
            half = [q for q in pts if q[0] >= 0]
            if len(half) >= 3:
                fpoly(surf, dark, [P(0, min(q[1] for q in pts))] + [P(*q) for q in half] + [P(0, max(q[1] for q in pts))], None)

    def ln(a, b2, col, w=1):
        fline(surf, col, P(*a), P(*b2), w)

    if k == "cowl":
        return _draw_helmet_front_v1(surf, hx, hy, u, item_id, view, facing)
    dome = [(-2.75, -0.3), (-2.6, -2.2), (-1.5, -3.45), (0, -3.8), (1.5, -3.45), (2.6, -2.2), (2.75, -0.3)]
    if k == "med_helm":
        if tier <= 2:
            # mail aventail behind (bulk) — sides/back of neck
            av = [(-2.9, -0.4), (2.9, -0.4), (3.1, 2.6), (1.6, 3.4), (-1.6, 3.4), (-3.1, 2.6)] if not side else \
                 [(-2.9, -0.6), (0.6, -0.6), (0.2, 2.8), (-1.6, 3.6), (-3.1, 2.6)]
            fpoly(surf, MATS["iron"][1] if tier == 2 else MATS["bronze"][1], [P(*q) for q in av])
            for yy in (0.6, 1.6, 2.6):
                ln((-2.6, yy), (2.6 if not side else 0.0, yy), MATS["steel"][0] if tier == 2 else MATS["bronze"][2])
            body(dome + [(2.75, 0.1), (-2.75, 0.1)])
            ln((-2.8, 0.0), (2.8, 0.0), trimc, max(1, u * 0.55))
            if tier == 2:   # kettle brim
                brim = [(-3.7, -0.2), (3.7, -0.2), (3.3, 0.5), (-3.3, 0.5)] if not side else [(-3.6, -0.3), (3.4, -0.3), (3.0, 0.4), (-3.2, 0.4)]
                fpoly(surf, b, [P(*q) for q in brim])
                for xx in (-2.6, -1.0, 1.0, 2.6):
                    pygame.draw.circle(surf, S["rivet"], tuple(map(int, P(xx, 0.15))), max(1, int(u * 0.25)))
            else:
                for xx in (-1.6, 1.6):
                    pygame.draw.circle(surf, S["rivet"], tuple(map(int, P(xx, -0.05))), max(1, int(u * 0.25)))
            if not back:
                nx = 1.4 if side else 0.0
                fpoly(surf, b, [P(nx - 0.4, 0.0), P(nx + 0.4, 0.0), P(nx + 0.3, 1.9), P(nx - 0.3, 1.9)])
            ln((-2.0, -2.4), (-0.6, -3.4), l)
            return
        if tier == 3:      # steel bascinet with snouted visor
            shell = dome + [(2.8, 1.6), (1.6, 3.1), (-1.6, 3.1), (-2.8, 1.6)]
            if side:
                shell = [(-2.8, 1.8), (-2.7, -2.2), (-1.4, -3.5), (0.3, -3.8), (1.8, -3.2), (2.6, -1.4), (3.6, 0.4), (2.4, 2.6), (0.6, 3.2), (-1.8, 3.2)]
            body(shell)
            if not back:
                ex = (0.4, 2.8) if side else (-2.0, 2.0)
                fpoly(surf, (22, 20, 24), [P(ex[0], -0.75), P(ex[1], -0.75), P(ex[1], -0.25), P(ex[0], -0.25)], None)
                for xx in ((1.6, 2.2) if side else (-0.9, 0, 0.9)):
                    pygame.draw.circle(surf, (22, 20, 24), tuple(map(int, P(xx, 1.3))), max(1, int(u * 0.2)))
                ln((0.0 if not side else 3.6, -3.6 if not side else 0.4), (0, 2.9) if not side else (2.0, -3.0), l)
            ln((-2.8, 1.7), (2.8, 1.7) if not side else (2.4, 2.6), trimc, max(1, u * 0.45))
            pygame.draw.lines(surf, trimc, False, [tuple(map(int, P(*q))) for q in shell[:len(dome)]], 1)
            return
        if tier == 4:      # mithril sallet: long tail, tall ridge crest, silver trim
            if side:
                shell = [(-3.8, 1.6), (-3.2, -1.0), (-2.2, -3.1), (0.2, -3.8), (1.9, -3.1), (2.7, -1.2), (2.9, 1.2), (1.4, 2.6), (-0.6, 1.4), (-2.2, 1.9)]
            else:
                shell = dome + [(2.9, 1.2), (1.8, 2.6), (-1.8, 2.6), (-2.9, 1.2)]
            fpoly(surf, trimc, [P(-0.35 if not side else -2.2, -3.6), P(0.35 if not side else 1.0, -3.6), P(0.2 if not side else 0.4, -4.3), P(-0.2 if not side else -1.6, -4.3)])
            body(shell)
            if not back:
                ex = (0.5, 2.9) if side else (-2.1, 2.1)
                fpoly(surf, (22, 22, 34), [P(ex[0], -0.7), P(ex[1], -0.7), P(ex[1], -0.15), P(ex[0], -0.15)], None)
            pygame.draw.lines(surf, trimc, True, [tuple(map(int, P(*q))) for q in shell], max(1, int(u * 0.4)))
            ln((0, -3.7), (0, -1.0) if not side else (0.2, -3.7), trimc)
            return
        # tier 5 adamant: flat-topped great helm, cross visor, brass trim, comb + plume
        plume_col = (150, 48, 40)
        if side or back:
            pl = [(-0.6, -3.7), (-2.6, -4.25), (-4.3, -3.2), (-4.0, -1.8), (-2.8, -2.8)] if side else [(-0.8, -3.6), (0.8, -3.6), (1.6, -2.0), (0, -1.2), (-1.6, -2.0)]
            fpoly(surf, plume_col, [P(*q) for q in pl])
        shell = [(-2.9, 2.9), (-2.95, -2.9), (-2.2, -3.5), (2.2, -3.5), (2.95, -2.9), (2.9, 2.9), (1.4, 3.3), (-1.4, 3.3)]
        body(shell)
        fpoly(surf, trimc, [P(-0.4, -3.5), P(0.4, -3.5), P(0.3, -4.2), P(-0.3, -4.2)])
        for yy in (-2.5, 2.4):
            ln((-2.9, yy), (2.9, yy), trimc, max(1, u * 0.45))
        if not back:
            x0, x1 = (0.2, 2.9) if side else (-2.2, 2.2)
            fpoly(surf, (20, 22, 20), [P(x0, -0.9), P(x1, -0.9), P(x1, -0.35), P(x0, -0.35)], None)
            ln((1.5 if side else 0.0, -0.35), (1.5 if side else 0.0, 2.0), (20, 22, 20), max(1, u * 0.4))
            for xx in ((2.2, 2.6) if side else (-1.3, 1.3)):
                for yy in (0.6, 1.3):
                    surf.set_at(tuple(map(int, P(xx, yy))), (20, 22, 20))
        return
    if k == "dragon_helm":
        # horns behind
        for sg in ((-1,) if side else (-1, 1)):
            if side:
                horn = [(-0.6, -2.6), (-2.2, -3.6), (-4.4, -4.25), (-5.2, -3.4), (-3.2, -2.9), (-1.4, -1.6)]
            else:
                horn = [(2.2 * sg, -2.0), (4.2 * sg, -2.6), (5.1 * sg, -4.25), (5.4 * sg, -3.0), (4.6 * sg, -1.6), (2.6 * sg, -0.9)]
            fpoly(surf, Gd[0], [P(*q) for q in horn], Gd[1])
            fline(surf, Gd[2], P(*horn[0]), P(*horn[2]), 1)
        # fin crest (red spines with gold edge)
        if side:
            for i, x in enumerate((1.0, -0.4, -1.8)):
                fpoly(surf, (170, 40, 36), [P(x + 0.7, -3.5), P(x - 0.5, -4.25), P(x - 0.8, -3.2)], Gd[1])
        shell = [(-2.9, 2.6), (-3.0, -1.2), (-2.1, -3.3), (0, -3.85), (2.1, -3.3), (3.0, -1.2), (2.9, 2.6), (1.3, 3.5), (-1.3, 3.5)]
        if side:
            shell = [(-2.9, 2.4), (-3.0, -1.2), (-2.0, -3.3), (0.2, -3.85), (2.0, -3.1), (2.8, -1.2), (4.0, 0.6), (3.6, 1.8), (1.8, 3.4), (-1.4, 3.4)]
        body(shell)
        pygame.draw.lines(surf, Gd[0], True, [tuple(map(int, P(*q))) for q in shell], max(1, int(u * 0.45)))
        if not back:
            # gold visor pattern: chevrons + central rib, cheek wings
            if side:
                for yy in (0.2, 1.2):
                    ln((1.6, yy - 0.8), (3.4, yy + 0.3), Gd[0])
                ln((0.2, -3.8), (3.8, 0.5), Gd[2])
                fpoly(surf, Gd[0], [P(-0.8, 0.6), P(1.2, 1.0), P(0.8, 2.8), P(-0.6, 2.2)], Gd[1])
                eye = [(1.7, -0.7)]
            else:
                for yy in (0.6, 1.6):
                    ln((-2.0, yy - 0.9), (0, yy), Gd[0])
                    ln((2.0, yy - 0.9), (0, yy), Gd[0])
                ln((0, -3.8), (0, 3.3), Gd[2], max(1, u * 0.35))
                for sg in (-1, 1):
                    fpoly(surf, Gd[0], [P(2.2 * sg, 0.2), P(3.0 * sg, 0.8), P(2.4 * sg, 2.6), P(1.6 * sg, 1.8)], Gd[1])
                eye = [(-1.1, -0.8), (1.1, -0.8)]
            for e in eye:
                A.gem(surf, P(*e), max(1, u * 0.32), (230, 30, 36), t)
        else:
            for i in range(3):
                A.rune(surf, P(0, -2.4 + i * 1.6), 1.2 * u, Gd[0], i)
        return
    if k == "grill_helm":
        # sun-ray crown + wings behind the helm
        for sg in ((-1,) if side else (-1, 1)):
            if side:
                wing = [(-1.4, -1.8), (-3.4, -3.6), (-5.0, -4.25), (-4.6, -3.0), (-5.2, -2.6), (-4.2, -1.9), (-4.6, -1.2), (-2.6, -0.6)]
            else:
                wing = [(2.6 * sg, -1.4), (3.8 * sg, -3.2), (4.9 * sg, -4.25), (4.8 * sg, -3.0), (5.4 * sg, -2.6), (4.6 * sg, -1.8), (5.0 * sg, -1.0), (3.0 * sg, -0.2)]
            fpoly(surf, Gd[0], [P(*q) for q in wing], Gd[1])
            fline(surf, Gd[1], P(*wing[0]), P(*wing[3]), 1)
            fline(surf, Gd[1], P(*wing[0]), P(*wing[5]), 1)
        for i in range(7):
            a = -math.pi / 2 + (i - 3) * 0.33
            r0, r1 = 3.4, (4.25 if i == 3 else 4.6)
            p0 = (math.cos(a) * r0 * (1 if not side else 0.8), -0.2 + math.sin(a) * r0)
            p1 = (math.cos(a) * r1 * (1 if not side else 0.8), -0.2 + math.sin(a) * r1)
            q0 = (math.cos(a - 0.12) * r0, -0.2 + math.sin(a - 0.12) * r0)
            q1 = (math.cos(a + 0.12) * r0, -0.2 + math.sin(a + 0.12) * r0)
            fpoly(surf, Gd[0], [P(*q0), P(*p1), P(*q1)], Gd[1])
        shell = [(-2.9, 2.7), (-3.0, -1.2), (-2.1, -3.3), (0, -3.8), (2.1, -3.3), (3.0, -1.2), (2.9, 2.7), (1.3, 3.5), (-1.3, 3.5)]
        body(shell)
        pygame.draw.lines(surf, Gd[0], True, [tuple(map(int, P(*q))) for q in shell], max(1, int(u * 0.45)))
        if not back:
            x0, x1 = (-0.4, 2.7) if side else (-2.0, 2.0)
            fpoly(surf, (12, 10, 14), [P(x0, -1.1), P(x1, -1.1), P(x1, 2.2), P(x0, 2.2)], None)
            n = 3 if side else 5
            for i in range(n + 1):
                xx = x0 + (x1 - x0) * i / n
                ln((xx, -1.1), (xx, 2.2), Gd[0], max(1, u * 0.3))
            ln((x0, -1.1), (x1, -1.1), Gd[0], max(1, u * 0.45))
            ln((x0, 0.6), (x1, 0.6), Gd[1])
            ln((x0, 2.2), (x1, 2.2), Gd[0], max(1, u * 0.4))
            A.gem(surf, P(0.9 if side else 0.0, -2.1), max(1, u * 0.42), (255, 176, 60), t)
            ln((0 if not side else 0.9, -3.7), (0 if not side else 0.9, -2.6), Gd[0], max(1, u * 0.35))
        else:
            A.eclipse_emblem(surf, P(0, -1.2), 1.3 * u, t, b)
        return


def _draw_royal_shield(surf, cx, cy, sc, item_id, look):
    """Mythos (dragon) kite and Eclipse aegis: gold filigree, big emblem, gem inlays."""
    import armour_v2 as A
    b, d, l = look["pal"]
    P = lambda x, y: (cx + x * sc, cy + y * sc)
    G = A.G
    if item_id == "mythos_shield":
        pts = [P(-4.0, -4.8), P(4.0, -4.8), P(3.8, 0.4), P(0, 6.4), P(-3.8, 0.4)]
        fpoly(surf, b, pts)
        fpoly(surf, d, [P(0, -4.8), P(4.0, -4.8), P(3.8, 0.4), P(0, 6.4)], None)
        pygame.draw.polygon(surf, G[0], [tuple(map(int, p)) for p in pts], max(2, int(sc * 0.6)))
        inner = [P(-3.1, -4.0), P(3.1, -4.0), P(2.9, 0.2), P(0, 5.2), P(-2.9, 0.2)]
        pygame.draw.polygon(surf, G[1], [tuple(map(int, p)) for p in inner], 1)
        A.dragon_emblem(surf, P(0, -0.8), 1.35 * sc, 0.0, b)
        for p in (P(-3.3, -4.2), P(3.3, -4.2), P(0, 5.4)):
            A.gem(surf, p, max(1, sc * 0.45), (230, 30, 36), None)
    else:
        R0 = 4.6
        pygame.draw.circle(surf, A.OUT, tuple(map(int, P(0, 0))), int(R0 * sc) + 1)
        pygame.draw.circle(surf, G[0], tuple(map(int, P(0, 0))), int(R0 * sc))
        pygame.draw.circle(surf, b, tuple(map(int, P(0, 0))), int((R0 - 0.8) * sc))
        pygame.draw.circle(surf, G[1], tuple(map(int, P(0, 0))), int((R0 - 1.4) * sc), 1)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            A.gem(surf, P(math.cos(a) * (R0 - 0.4), math.sin(a) * (R0 - 0.4)), max(1, sc * 0.35), (150, 70, 220) if i % 2 else (255, 176, 60), None)
        A.eclipse_emblem(surf, P(0, 0), 1.9 * sc, 0.0, b)
