"""
equipment_ui_v2.py: Equipment & Stats screen, v2 restyle (EQUIPMENT_SCREEN_STYLE_SPEC.md sections 9 and 10).

* Logical window 900x640 (equipment_layout_wireframe.png coordinates). It sits over the world view
  (the 900x640 map area), scales down evenly when the space is smaller, and below a 0.7 scale the
  panels stack (equipment on top, stats below, mouse wheel scrolls).
* No slot ever overlaps the character: NO_SLOT_ZONE is checked by tests and drawn in debug mode.
* One click on an inventory item equips it (the server swaps a full slot); one click on a filled
  slot unequips it. No drag. Every change flashes the slot gold and plays a clank.
* The paper doll is the player's own figure (chosen face and outfit, worn gear), fitted to FIGURE_BOX.
* Server still validates every EQUIP / UNEQUIP (server.handle_equip / handle_unequip).
"""
import math
import os
import time
import pygame
import logging
import traceback

LOG = logging.getLogger("crownfall.equipment_ui")
_LOGGED = set()


def _log_once(where, exc):
    """Log a draw failure once per (section, error) so a broken frame never floods the log."""
    key = (where, type(exc).__name__, str(exc)[:120])
    if key in _LOGGED:
        return
    _LOGGED.add(key)
    msg = f"equipment screen: {where} failed: {exc!r}\n{traceback.format_exc()}"
    LOG.error(msg)
    if not logging.getLogger().handlers and not LOG.handlers:   # no logging set up: still say it somewhere
        try:
            import sys
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass


def _opaque(w, h):
    """An opaque RGB surface. A plain pygame.Surface((w, h)) copies the display's pixel format, and on a
    real macOS (cocoa) window that format carries an alpha mask: fills then land with alpha 0 and the
    whole window turns see-through (only outlines and bars survived). Explicit no-alpha masks fix that."""
    return pygame.Surface((max(1, int(w)), max(1, int(h))), 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))

BASE_W, BASE_H = 900, 640
STACK_SCALE = 0.7            # below this the panels stack
STACK_W = 452                # stacked canvas width (left panel + margins)
EDGE_GAP = 16

# ---- palette (spec section 7 / 9) ----
OVERLAY = (2, 3, 5)
WOOD = (42, 30, 20)
WOOD_DK = (18, 12, 8)
WOOD_HI = (90, 70, 48)
WINDOW_BG = (26, 20, 14)
PANEL = (43, 34, 25)
PANEL_RIM = (90, 70, 48)
CELL = (40, 31, 24)
CELL_RIM = (138, 106, 62)
CELL_IN = (58, 46, 34)
GOLD = (179, 148, 101)
GOLD_HI = (230, 203, 142)
TITLE_GOLD = (206, 174, 115)
GLOW = (242, 193, 78)
FLASH = (255, 211, 107)
PLAQUE = (28, 21, 15)
ROW = (31, 24, 18)
ROW_RIM = (58, 46, 34)
TILE = (36, 28, 21)
TEXT = (234, 219, 192)
MUTED = (168, 154, 132)
GAIN = (63, 125, 58)
GAIN_TXT = (110, 190, 100)
LOSS = (158, 43, 37)
LOSS_TXT = (225, 95, 85)
ATT_C = (217, 100, 74)
STR_C = (224, 177, 62)
DEF_C = (92, 143, 214)
RNG_C = (127, 191, 90)
KARMA_C = (185, 166, 232)
COMBAT_C = (155, 212, 138)
WEAPON_C = (224, 177, 62)
SILH = (110, 102, 92)

# ---- wireframe geometry (window-relative, 1x) ----
SLOT = 56
SLOTS = {
    "cape": (120, 80), "helmet": (212, 80), "amulet": (304, 80),
    "weapon": (40, 160), "body": (40, 232), "legs": (40, 304), "boots": (40, 376),
    "shield": (356, 160), "gloves": (356, 232), "ring": (356, 304), "ammo": (356, 376),
    "tool_woodcutting": (120, 466), "tool_mining": (212, 466), "tool_fishing": (304, 466),
}
SLOT_LABELS = {
    "cape": "Cape", "helmet": "Head", "amulet": "Amulet", "weapon": "Weapon", "body": "Body",
    "legs": "Legs", "boots": "Boots", "shield": "Shield", "gloves": "Gloves", "ring": "Ring",
    "ammo": "Ammo", "tool_woodcutting": "Axe", "tool_mining": "Pickaxe", "tool_fishing": "Net",
}
TOOL_SLOTS = ("tool_woodcutting", "tool_mining", "tool_fishing")
# Slots the server stores today. Cape / gloves / boots are drawn (empty silhouettes) and become live
# as soon as items with those equip slots exist; the server refuses them until then.
LIVE_SLOTS = ("helmet", "amulet", "ring", "weapon", "ammo", "shield", "body", "legs") + TOOL_SLOTS
NO_SLOT_ZONE = pygame.Rect(108, 152, 236, 290)
FIGURE_BOX = pygame.Rect(120, 164, 212, 266)
TITLE_RECT = pygame.Rect(16, 8, 300, 44)
NAME_RECT = pygame.Rect(584, 8, 300, 44)
EQUIP_ALL_RECT = pygame.Rect(328, 12, 112, 36)   # between the title and the name plate (fits the stacked canvas too)
LEFT_PANEL = pygame.Rect(16, 64, 420, 540)
RIGHT_PANEL = pygame.Rect(452, 64, 432, 540)
TOOLTIP = pygame.Rect(32, 540, 388, 56)
TOOLS_LABEL_Y = 448
FOOTER_Y = 610
BONUS_ROWS_Y = (104, 150, 196, 242)
LEVEL_TILES = ((468, 316), (672, 316), (468, 368), (672, 368))
HP_RECT = pygame.Rect(468, 420, 400, 40)
INFO_RECT = pygame.Rect(468, 470, 400, 82)
FLASH_S = 0.3
DELTA_S = 1.5
TICK_S = 0.4
FOOTER = "Hover a slot for details  ·  Click an item to equip  ·  Click a slot to unequip  ·  Esc / E to close"


def _slot_hint(slot):
    """Tooltip hint. Body and legs are separate (David, 29 Oct 2026): one alone shows the plain base."""
    if slot in ("body", "legs"):
        return f"{slot.title()} slot  ·  Body + legs of one tier make the full set  ·  Click slot to unequip"
    if slot in TOOL_SLOTS:
        return f"{SLOT_LABELS[slot]}  ·  Keep worn while you fight  ·  Click slot to unequip"
    return f"{slot.title()} slot  ·  Click slot to unequip"


def slot_rects():
    """Logical (window-relative) rect per slot."""
    return {s: pygame.Rect(x, y, SLOT, SLOT) for s, (x, y) in SLOTS.items()}


def overlaps_character():
    """Slots (or their labels) that touch the no-slot zone. Must stay empty (spec 10, hard rule)."""
    bad = []
    for s, r in slot_rects().items():
        lab = r.copy() if s not in TOOL_SLOTS else pygame.Rect(r.x - 6, r.bottom + 2, r.w + 12, 16)
        glow = r.inflate(8, 8)
        if NO_SLOT_ZONE.colliderect(glow) or NO_SLOT_ZONE.colliderect(lab):
            bad.append(s)
    return bad


# ---------------------------------------------------------------- layout / scaling
def viewport(client):
    """Space the window may use: the world view left of the sidebar (or the whole window if narrow)."""
    sw, sh = client.screen.get_size()
    side = 300
    if sw - side >= 420:
        return pygame.Rect(0, 0, sw - side, sh if sh < BASE_H + 160 else min(sh, BASE_H))
    return pygame.Rect(0, 0, sw, sh)


def layout(vw, vh):
    """{mode, scale, ox, oy, w, h, canvas} for a viewport of vw x vh px."""
    if vw >= BASE_W and vh >= BASE_H:
        s = 1.0
    else:
        s = min(1.0, (vw - 2 * EDGE_GAP) / BASE_W, (vh - 2 * EDGE_GAP) / BASE_H)
    if s >= STACK_SCALE:
        w, h = int(BASE_W * s), int(BASE_H * s)
        return {"mode": "full", "scale": s, "ox": (vw - w) // 2, "oy": (vh - h) // 2, "w": w, "h": h,
                "canvas": (BASE_W, BASE_H)}
    # stacked: equipment panel on top, stats below; width-fitted, height scrolls
    s2 = min(1.0, (vw - 2 * EDGE_GAP) / STACK_W)
    w = int(STACK_W * s2)
    h = min(vh - 2 * EDGE_GAP, int(STACK_H * s2))
    return {"mode": "stack", "scale": s2, "ox": (vw - w) // 2, "oy": EDGE_GAP, "w": w, "h": h,
            "canvas": (STACK_W, STACK_H)}


STACK_DY = 600               # stats panel origin in the stacked canvas
STACK_H = STACK_DY + 540 + 60
_RIGHT_DX = RIGHT_PANEL.x - 16   # move the stats panel to x16 when stacked


def _to_logical(client, mx, my):
    L = getattr(client, "_equip_layout", None)
    if not L:
        return None
    vp = L["vp"]
    lx = (mx - vp.x - L["ox"]) / L["scale"]
    ly = (my - vp.y - L["oy"]) / L["scale"] + (getattr(client, "equip_scroll", 0) if L["mode"] == "stack" else 0)
    if not (0 <= mx - vp.x - L["ox"] < L["w"] and 0 <= my - vp.y - L["oy"] < L["h"]):
        return None
    return lx, ly


def window_rect(client):
    L = getattr(client, "_equip_layout", None)
    if not L:
        return pygame.Rect(0, 0, BASE_W, BASE_H)
    return pygame.Rect(L["vp"].x + L["ox"], L["vp"].y + L["oy"], L["w"], L["h"])


def _slot_logical_rects(mode):
    rects = slot_rects()
    return rects


def _screen_rect(L, r, scroll=0):
    s = L["scale"]
    return pygame.Rect(L["vp"].x + L["ox"] + int(r.x * s), L["vp"].y + L["oy"] + int((r.y - scroll) * s),
                       max(1, int(r.w * s)), max(1, int(r.h * s)))


# ---------------------------------------------------------------- fonts / sound / art
_FONTS = {}
_FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))


def font(kind, size):
    key = (kind, size)
    if key not in _FONTS:
        path = os.path.join(_FONT_DIR, "Cinzel.ttf" if kind == "title" else "EBGaramond.ttf")
        f = None
        for make in (lambda: pygame.font.Font(path, size),
                     lambda: pygame.font.SysFont("georgia,times new roman,serif", size),
                     lambda: pygame.font.SysFont("helvetica neue,helvetica,arial,dejavusans", size),
                     lambda: pygame.font.Font(None, size)):          # pygame's bundled font: always there
            try:
                f = make()
                f.render("Ag", True, (255, 255, 255))                 # prove it can actually draw
                break
            except Exception as e:
                _log_once(f"font {kind}/{size}", e)
                f = None
        if f is None:
            if not pygame.font.get_init():
                pygame.font.init()
            f = pygame.font.Font(None, size)
        if kind == "bold":
            f.set_bold(True)
        _FONTS[key] = f
    return _FONTS[key]


_SOUND = {}


def play_clank():
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "sounds", "equip_clank.wav"))
    try:
        if "clank" not in _SOUND:
            if not pygame.mixer.get_init():
                return False
            _SOUND["clank"] = pygame.mixer.Sound(path)
            _SOUND["clank"].set_volume(0.55)
        _SOUND["clank"].play()
        return True
    except Exception:
        return False


_ART = {}


def _grain(w, h, base, seed, streak=True):
    """Procedural wood / leather grain (cached)."""
    key = ("grain", w, h, base, seed, streak)
    if key in _ART:
        return _ART[key]
    import random
    rnd = random.Random(seed)
    s = _opaque(w, h)
    s.fill(base)
    if streak:
        for _ in range(h // 2):
            y = rnd.randrange(h)
            d = rnd.choice((-6, -4, -3, 3, 4))
            c = tuple(max(0, min(255, v + d)) for v in base)
            amp, ph, fq = rnd.uniform(1, 4), rnd.uniform(0, 6.3), rnd.uniform(0.004, 0.02)
            pts = [(x, int(y + amp * math.sin(ph + x * fq))) for x in range(0, w + 8, 8)]
            if len(pts) > 1:
                pygame.draw.lines(s, c, False, pts, 1)
    for _ in range(w * h // 60):
        x, y = rnd.randrange(w), rnd.randrange(h)
        d = rnd.randint(-7, 5)
        s.set_at((x, y), tuple(max(0, min(255, v + d)) for v in base))
    _ART[key] = s
    return s


def _soft_shadow(surf, rect, radius=6, strength=150, inset=True):
    """Inner shadow (inset) for recessed panels."""
    sh = pygame.Surface(rect.size, pygame.SRCALPHA)
    for i in range(radius * 3):
        a = int(strength * (1 - i / (radius * 3)) ** 2)
        pygame.draw.rect(sh, (0, 0, 0, a), sh.get_rect().inflate(-2 * i, -2 * i), 1, border_radius=max(0, 6 - i))
    surf.blit(sh, rect.topleft)


def _filigree(surf, cx, cy, fx, fy, size=78):
    """Gold filigree corner ornament; (fx, fy) = +1/-1 direction into the window."""
    def P(x, y):
        return (int(cx + fx * x), int(cy + fy * y))
    w = 2
    for col, off in ((WOOD_DK, 1), (GOLD, 0)):
        o = off
        pygame.draw.lines(surf, col, False, [P(4 + o, size + o), P(4 + o, 4 + o), P(size + o, 4 + o)], w + 1)
        pygame.draw.lines(surf, col, False, [P(10 + o, size * 0.7 + o), P(10 + o, 10 + o), P(size * 0.7 + o, 10 + o)], 1)
        # scrolls
        for (ax, ay, r, a0, a1) in ((22, 22, 12, 0, 1.5 * math.pi), (40, 14, 7, math.pi * 0.2, math.pi * 1.6),
                                    (14, 40, 7, -math.pi * 0.4, math.pi * 1.0), (54, 10, 5, 0, math.pi * 1.8),
                                    (10, 54, 5, 0, math.pi * 1.8)):
            pts = []
            for k in range(18):
                t = a0 + (a1 - a0) * k / 17
                rr = r * (1 - 0.55 * k / 17)
                pts.append(P(ax + o + rr * math.cos(t), ay + o + rr * math.sin(t)))
            pygame.draw.lines(surf, col, False, pts, w)
    pygame.draw.circle(surf, GOLD_HI, P(22, 22), 3)
    for d in (30, 46, 62):
        pygame.draw.circle(surf, GOLD, P(d, 4), 2)
        pygame.draw.circle(surf, GOLD, P(4, d), 2)


def _diamond(surf, cx, cy, r, col):
    pygame.draw.polygon(surf, col, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])


def _plaque(surf, rect, rim=GOLD, fill=PLAQUE, radius=4):
    pygame.draw.rect(surf, (0, 0, 0), rect.move(0, 2), border_radius=radius)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, rim, rect, 1, border_radius=radius)
    pygame.draw.rect(surf, (rim[0] // 3, rim[1] // 3, rim[2] // 3), rect.inflate(-4, -4), 1, border_radius=radius)


def _panel(surf, rect, seed):
    pygame.draw.rect(surf, (0, 0, 0), rect.move(0, 3), border_radius=6)
    surf.blit(_grain(rect.w, rect.h, PANEL, seed, streak=False), rect.topleft)
    _soft_shadow(surf, rect, 8, 170)
    pygame.draw.rect(surf, PANEL_RIM, rect, 1, border_radius=6)
    pygame.draw.rect(surf, (20, 15, 10), rect.inflate(2, 2), 1, border_radius=7)


def _text(surf, txt, f, col, pos, shadow=True, anchor="topleft"):
    try:
        img = f.render(txt, True, col)
    except Exception as e:                                   # broken font object: use pygame's own
        _log_once("text render", e)
        f = pygame.font.Font(None, max(10, f.get_height() if hasattr(f, "get_height") else 18))
        img = f.render(txt, True, col)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(f.render(txt, True, (0, 0, 0)), r.move(1, 1))
    surf.blit(img, r)
    return r


def _silhouette(surf, slot, r, col=(78, 70, 58)):
    """Faded slot glyph for empty slots (OSRS-style)."""
    cx, cy = r.center
    u = r.w / 16.0
    P = lambda x, y: (int(cx + x * u), int(cy + y * u))
    if slot == "helmet":
        pygame.draw.polygon(surf, col, [P(-4.5, 3), P(-4.5, -1), P(-2.6, -4.4), P(0, -5.2), P(2.6, -4.4), P(4.5, -1), P(4.5, 3), P(2.6, 3), P(2.6, 0), P(-2.6, 0), P(-2.6, 3)])
    elif slot == "amulet":
        pygame.draw.arc(surf, col, pygame.Rect(P(-4.5, -6)[0], P(0, -6)[1], int(9 * u), int(9 * u)), math.pi, 2 * math.pi, max(2, int(u)))
        pygame.draw.lines(surf, col, False, [P(-4.5, -1.5), P(0, 2.5), P(4.5, -1.5)], max(2, int(u)))
        pygame.draw.circle(surf, col, P(0, 4), int(2.2 * u))
    elif slot == "ammo":
        for o in (-2.5, 0, 2.5):
            pygame.draw.line(surf, col, P(-4 + o, 5), P(4 + o, -5), max(2, int(u)))
            pygame.draw.polygon(surf, col, [P(4 + o, -5), P(2 + o, -4.4), P(3.4 + o, -3)])
    elif slot == "weapon":
        pygame.draw.polygon(surf, col, [P(-5, 5), P(-3.6, 5.6), P(4.8, -2.8), P(5.4, -5.4), P(2.8, -4.8), P(-5.6, 3.6)])
        pygame.draw.line(surf, col, P(-4.6, 1.2), P(-1.2, 4.6), max(2, int(u * 1.4)))
    elif slot == "shield":
        pygame.draw.polygon(surf, col, [P(-4.6, -5), P(4.6, -5), P(4.2, 0.6), P(0, 6), P(-4.2, 0.6)])
    elif slot == "body":
        pygame.draw.polygon(surf, col, [P(-3, -5.4), P(0, -4), P(3, -5.4), P(6, -3.4), P(6, 1), P(3.6, 1), P(3.4, 5.6), P(-3.4, 5.6), P(-3.6, 1), P(-6, 1), P(-6, -3.4)])
    elif slot == "legs":
        pygame.draw.polygon(surf, col, [P(-4, -5.6), P(4, -5.6), P(4.6, 5.6), P(1.2, 5.6), P(0, -1), P(-1.2, 5.6), P(-4.6, 5.6)])
    elif slot == "ring":
        pygame.draw.circle(surf, col, P(0, 1), int(4.2 * u), max(2, int(u * 1.3)))
    elif slot in ("tool", "tool_mining"):   # pickaxe: handle + curved head
        pygame.draw.line(surf, col, P(-4.6, 5.2), P(2.2, -1.6), max(2, int(u * 1.5)))
        pygame.draw.polygon(surf, col, [P(-1.8, -5.2), P(2.6, -3.6), P(5.6, 0.2), P(4.4, 0.8), P(1.8, -2.2), P(-2.2, -3.8)])
        pygame.draw.circle(surf, col, P(0, -3.6), int(1.8 * u))
    elif slot == "tool_woodcutting":  # hatchet
        pygame.draw.line(surf, col, P(-3.5, 5.2), P(3.5, -4.5), max(2, int(u * 1.4)))
        pygame.draw.polygon(surf, col, [P(0.5, -5.2), P(5.2, -3.2), P(5.6, -0.2), P(2.2, -1.8), P(-0.4, -3.6)])
    elif slot == "tool_fishing":  # net diamond
        pygame.draw.polygon(surf, col, [P(0, -5), P(5, 0), P(0, 5), P(-5, 0)], max(2, int(u)))
        pygame.draw.line(surf, col, P(-2.5, -2.5), P(2.5, 2.5), max(1, int(u)))
        pygame.draw.line(surf, col, P(2.5, -2.5), P(-2.5, 2.5), max(1, int(u)))


def _silhouette_extra(surf, slot, r, col):
    cx, cy = r.center
    u = r.w / 16.0
    P = lambda x, y: (int(cx + x * u), int(cy + y * u))
    if slot == "cape":
        pygame.draw.polygon(surf, col, [P(-2.5, -5.5), P(2.5, -5.5), P(4, -3), P(5.5, 5.5), P(0, 4.5), P(-5.5, 5.5), P(-4, -3)])
        pygame.draw.line(surf, (0, 0, 0, 0), P(0, -3), P(0, 4), 1)
    elif slot == "gloves":
        pygame.draw.polygon(surf, col, [P(-3.5, 5.5), P(-3.5, -1), P(-4.5, -3.5), P(-3, -4), P(-2, -1.5), P(-2, -5.5), P(-0.6, -5.5),
                                        P(-0.4, -2), P(0.4, -6), P(1.8, -6), P(1.8, -2), P(2.6, -5.2), P(4, -5), P(3.6, 0), P(3, 5.5)])
    elif slot == "boots":
        for o in (-3.0, 2.2):
            pygame.draw.polygon(surf, col, [P(o - 1.6, -5.5), P(o + 1.4, -5.5), P(o + 1.4, 3), P(o + 3.2, 3.6), P(o + 3.2, 5.5), P(o - 1.8, 5.5)])


def _icon(surf, rect, item_id):
    try:
        import realistic_item_icons
        if realistic_item_icons.draw_icon(surf, rect, item_id):
            return True
    except Exception:
        pass
    try:
        import sprites
        img = sprites.get_item_sprite(item_id) if hasattr(sprites, "get_item_sprite") else None
        if img:
            surf.blit(pygame.transform.smoothscale(img, rect.size), rect.topleft)
            return True
    except Exception:
        pass
    return False


def _draw_silhouette(surf, slot, rect):
    tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
    r = tmp.get_rect()
    col = SILH
    if slot in ("cape", "gloves", "boots"):
        _silhouette_extra(tmp, slot, r, col)
    else:
        _silhouette(tmp, slot, r, col)
    tmp.set_alpha(110)
    surf.blit(tmp, rect.topleft)


# ---------------------------------------------------------------- paper doll
_DOLL_FIT = {}


def _look_key(appearance, eq):
    import json
    try:
        return json.dumps([appearance, eq], sort_keys=True, default=str)
    except Exception:
        return repr((appearance, eq))


def _draw_doll(client, surf, eq):
    """The player's own figure (chosen face + outfit + worn gear) fitted to FIGURE_BOX, feet on the spotlight."""
    import player_hd_client
    import eclipse_fx
    p = client.player or {}
    sex = "female" if (p.get("gender") or "male") == "female" else "male"
    appearance = p.get("appearance") or player_hd_client.get_default_appearance(sex)
    off = pygame.Surface((300, 300), pygame.SRCALPHA)
    feet = (150, 286)
    player_hd_client.draw_player(
        off, sex, appearance, feet[0], feet[1], 80, time.time(),
        anim="idle", facing="s", equipment=eq, fx_seed=eclipse_fx.player_seed(p.get("id")),
    )
    key = _look_key(appearance, eq)
    fit = _DOLL_FIT.get(key)
    if fit is None:
        # fit the figure itself (no sparkle aura) to FIGURE_BOX; the aura is clipped to the zone below
        bare = pygame.Surface((300, 300), pygame.SRCALPHA)
        player_hd_client.draw_player(bare, sex, appearance, feet[0], feet[1], 80, 0.0,
                                     anim="idle", facing="s", equipment=eq)
        bb = bare.get_bounding_rect(min_alpha=60)
        if bb.w < 4 or bb.h < 4:
            return None
        bb = bb.inflate(8, 8).clip(off.get_rect())
        k = min(FIGURE_BOX.w / bb.w, FIGURE_BOX.h / bb.h)
        fit = (bb, k)
        _DOLL_FIT.clear()
        _DOLL_FIT[key] = fit
    bb, k = fit
    crop = off.subsurface(bb)
    img = pygame.transform.smoothscale(crop, (max(1, int(bb.w * k)), max(1, int(bb.h * k))))
    r = img.get_rect(midbottom=(FIGURE_BOX.centerx, FIGURE_BOX.bottom))
    clip = surf.get_clip()
    surf.set_clip(NO_SLOT_ZONE.clip(clip) if clip else NO_SLOT_ZONE)
    surf.blit(img, r)
    surf.set_clip(clip)
    r = r.clip(FIGURE_BOX)
    client._equip_doll_rect = r.copy()
    client._equip_doll_look = appearance
    return r


# ---------------------------------------------------------------- stats helpers
def _bonuses(client, ITEMS, karma_slot_bonus):
    p = client.player or {}
    eq = p.get("equipment") or {}
    karma_lvl = (p.get("levels") or {}).get("karma", 1)
    b = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    for slot in ("helmet", "amulet", "ring", "weapon", "ammo", "shield", "body", "legs"):
        iid = eq.get(slot)
        if not iid:
            continue
        item = ITEMS.get(iid) or {}
        kb = karma_slot_bonus(slot, karma_lvl)
        for k in b:
            b[k] += int(item.get(k, 0) or 0) + int(kb.get(k, 0) or 0)
    return p.get("gear_bonuses") or b


def _anim_value(client, key, val):
    """Tick numbers to the new value over 0.4s; remember the +n/-n delta for 1.5s."""
    st = client.__dict__.setdefault("_equip_ticks", {})
    now = time.time()
    cur = st.get(key)
    if cur is None:
        st[key] = {"from": val, "to": val, "t": 0.0, "delta": 0}
        return val, 0, 0.0
    if cur["to"] != val:
        shown = _anim_value_now(cur, now)
        st[key] = {"from": shown, "to": val, "t": now, "delta": val - cur["to"]}
        cur = st[key]
    shown = _anim_value_now(cur, now)
    age = now - cur["t"]
    return shown, (cur["delta"] if age < DELTA_S else 0), age


def _anim_value_now(cur, now):
    a = min(1.0, (now - cur["t"]) / TICK_S) if cur["t"] else 1.0
    return int(round(cur["from"] + (cur["to"] - cur["from"]) * a))


def _glyph(scr, kind, cx, cy, col):
    if kind == "att":
        pygame.draw.line(scr, col, (cx - 9, cy + 9), (cx + 9, cy - 9), 3)
        pygame.draw.line(scr, col, (cx - 9, cy + 2), (cx - 2, cy + 9), 3)
    elif kind == "str":
        pygame.draw.polygon(scr, col, [(cx - 8, cy - 9), (cx + 8, cy - 9), (cx + 8, cy + 2), (cx, cy + 9), (cx - 8, cy + 2)])
        pygame.draw.rect(scr, (0, 0, 0), (cx - 8, cy - 9, 16, 4), 1)
    elif kind == "def":
        pygame.draw.polygon(scr, col, [(cx - 9, cy - 9), (cx + 9, cy - 9), (cx + 8, cy + 2), (cx, cy + 10), (cx - 8, cy + 2)])
    else:
        pygame.draw.arc(scr, col, pygame.Rect(cx - 9, cy - 10, 12, 20), -math.pi / 2, math.pi / 2, 3)
        pygame.draw.line(scr, col, (cx - 3, cy - 10), (cx - 3, cy + 10), 1)


# ---------------------------------------------------------------- drawing
def _draw_frame(c, w, h):
    c.blit(_grain(w, h, WINDOW_BG, 11), (0, 0))
    r = c.get_rect()
    pygame.draw.rect(c, WOOD, r, 6)
    pygame.draw.rect(c, WOOD_HI, r.inflate(-2, -2), 1)
    pygame.draw.rect(c, WOOD_DK, r.inflate(-10, -10), 2)
    pygame.draw.rect(c, GOLD, r.inflate(-14, -14), 1)
    for (x, y, fx, fy) in ((2, 2, 1, 1), (w - 3, 2, -1, 1), (2, h - 3, 1, -1), (w - 3, h - 3, -1, -1)):
        _filigree(c, x, y, fx, fy)
    # crest finial on the top edge
    cx = w // 2
    _diamond(c, cx, 7, 7, WOOD_DK)
    _diamond(c, cx, 7, 5, GOLD)
    _diamond(c, cx, 7, 2, GOLD_HI)


def _draw_title(client, c, dx=0, dy=0, name_rect=None):
    tr = TITLE_RECT.move(dx, dy)
    _plaque(c, tr)
    f = font("title", 24)
    _text(c, "Equipment & Stats", f, TITLE_GOLD, (tr.centerx, tr.centery + 1), anchor="center")
    for sx in (tr.x + 10, tr.right - 10):
        _diamond(c, sx, tr.centery, 4, GOLD)
    p = client.player or {}
    name = p.get("name") or "You"
    nr = name_rect or NAME_RECT
    _text(c, f"{name}   ·   Combat {client.player_combat_level()}", font("body", 20), TEXT,
          (nr.right - 4, nr.centery + 1), anchor="midright")


def _draw_equip_all(client, c, mouse):
    r = EQUIP_ALL_RECT
    hot = bool(mouse and r.collidepoint(mouse))
    t = time.time()
    fl = getattr(client, "_equip_all_flash", 0.0)
    if hot or t - fl < FLASH_S:
        g = pygame.Surface((r.w + 16, r.h + 16), pygame.SRCALPHA)
        a = 120 if t - fl < FLASH_S else 70
        for i in range(8):
            pygame.draw.rect(g, (*GLOW, max(0, a - i * 14)), g.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=8)
        c.blit(g, (r.x - 8, r.y - 8))
    _plaque(c, r, rim=GOLD_HI if hot else GOLD)
    _text(c, "Equip all", font("title", 17), GOLD_HI if hot else TITLE_GOLD, (r.centerx, r.centery + 1), anchor="center")


def _draw_left(client, c, ITEMS, karma_slot_bonus, mouse):
    p = client.player or {}
    eq = p.get("equipment") or {}
    inv = p.get("inventory") or {}
    _panel(c, LEFT_PANEL, 21)
    import eclipse_fx
    tier = eclipse_fx.fx_tier(eq)
    # spotlight ellipse at the figure's feet (tinted gold with a set glow)
    spot = pygame.Surface((NO_SLOT_ZONE.w, 70), pygame.SRCALPHA)
    for i in range(14):
        a = int((60 if tier else 38) * (1 - i / 14))
        pygame.draw.ellipse(spot, (*TITLE_GOLD, a), spot.get_rect().inflate(-i * 14, -i * 4))
    c.blit(spot, (NO_SLOT_ZONE.x, FIGURE_BOX.bottom - 36))
    halo = pygame.Surface(NO_SLOT_ZONE.size, pygame.SRCALPHA)
    for i in range(10):
        pygame.draw.ellipse(halo, (*TITLE_GOLD, 5), halo.get_rect().inflate(-i * 18, -i * 22))
    c.blit(halo, NO_SLOT_ZONE.topleft)
    _draw_doll(client, c, eq)
    if getattr(client, "debug_equip_zone", False):
        pygame.draw.rect(c, (230, 80, 60), NO_SLOT_ZONE, 1)
        pygame.draw.rect(c, (230, 200, 60), FIGURE_BOX, 1)

    hover = None
    now = time.time()
    flashes = client.__dict__.setdefault("_equip_flash", {})
    pulse = 0.5 + 0.5 * math.sin(now * math.pi)       # 2s set-glow pulse
    for slot, r in slot_rects().items():
        iid = eq.get(slot)
        hov = mouse is not None and r.collidepoint(mouse)
        if hov:
            hover = slot
        set_piece = bool(tier and iid and slot in ("helmet", "body", "legs", "shield", "weapon", "amulet", "ring")
                         and "eclipse" in str(iid))
        if hov or set_piece:
            g = pygame.Surface((r.w + 20, r.h + 20), pygame.SRCALPHA)
            ga = 90 if hov else int(50 + 50 * pulse)
            for i in range(8):
                pygame.draw.rect(g, (*GLOW, int(ga * (1 - i / 8))), g.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=8)
            c.blit(g, (r.x - 10, r.y - 10))
        pygame.draw.rect(c, (0, 0, 0), r.move(0, 2), border_radius=4)
        pygame.draw.rect(c, CELL, r, border_radius=4)
        _soft_shadow(c, r, 3, 200)
        rim = GOLD_HI if hov else (FLASH if set_piece else (GOLD if iid else CELL_RIM))
        pygame.draw.rect(c, rim, r, 2, border_radius=4)
        pygame.draw.rect(c, CELL_IN, r.inflate(-6, -6), 1, border_radius=3)
        tool = slot in TOOL_SLOTS
        inner = r.inflate(-10, -10) if tool else pygame.Rect(r.x + 9, r.y + 15, r.w - 18, r.h - 18)
        if not (iid and _icon(c, inner, iid)):
            _draw_silhouette(c, slot, inner)
        if slot == "ammo" and iid:
            if iid == "arrow_quiver":
                qn = int(p.get("quiver_total") or 0)
            else:
                qn = sum(int(e.get("qty") or 0) for e in inv.values() if e and e.get("item_id") == iid)
            _text(c, str(qn), font("bold", 13), FLASH, (r.x + 4, r.bottom - 16))
        lab = font("body", 13)
        if tool:
            _text(c, SLOT_LABELS[slot], font("body", 14), TEXT if iid else MUTED, (r.centerx, r.bottom + 2), anchor="midtop")
        else:   # label inside the slot's top edge (wireframe), so it never crowds the slot above
            _text(c, SLOT_LABELS[slot], lab, TEXT, (r.centerx, r.y + 1), anchor="midtop")
        t0 = flashes.get(slot)
        if t0 is not None and now - t0 < FLASH_S:
            a = 1 - (now - t0) / FLASH_S
            fl = pygame.Surface((r.w + 16, r.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(fl, (*FLASH, int(150 * a)), fl.get_rect().inflate(-8, -8), border_radius=6)
            for i in range(8):
                pygame.draw.rect(fl, (*FLASH, int(200 * a * (1 - i / 8))), fl.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=8)
            c.blit(fl, (r.x - 8, r.y - 8))
    # Tools label and rule
    ty = TOOLS_LABEL_Y
    _text(c, "Tools", font("title", 14), TITLE_GOLD, (LEFT_PANEL.centerx, ty + 4), anchor="center")
    for x0, x1 in ((NO_SLOT_ZONE.x + 6, LEFT_PANEL.centerx - 34), (LEFT_PANEL.centerx + 34, NO_SLOT_ZONE.right - 6)):
        pygame.draw.line(c, (GOLD[0] // 2, GOLD[1] // 2, GOLD[2] // 2), (x0, ty + 4), (x1, ty + 4), 1)
    _draw_tooltip(client, c, ITEMS, karma_slot_bonus, hover)
    return hover


def _draw_tooltip(client, c, ITEMS, karma_slot_bonus, hover):
    p = client.player or {}
    eq = p.get("equipment") or {}
    inv = p.get("inventory") or {}
    _plaque(c, TOOLTIP)
    slot = hover
    if slot is None:
        slot = next((s for s in ("weapon", "body", "helmet", "shield", "legs", "amulet", "ring", "ammo") if eq.get(s)), None)
    if slot is None:
        _text(c, "No gear worn. Click an item in your bag to wear it.", font("body", 16), MUTED,
              (TOOLTIP.x + 14, TOOLTIP.centery), anchor="midleft")
        return
    iid = eq.get(slot)
    item = ITEMS.get(iid) if iid else None
    if not item:
        live = slot in LIVE_SLOTS
        _text(c, f"{SLOT_LABELS.get(slot, slot)}: empty", font("title", 16), GOLD_HI, (TOOLTIP.x + 14, TOOLTIP.y + 8))
        _text(c, "Click an item in your bag to wear it" if live else "No items for this slot yet",
              font("body", 14), MUTED, (TOOLTIP.x + 14, TOOLTIP.y + 31))
        return
    ic = pygame.Rect(TOOLTIP.x + 8, TOOLTIP.y + 6, 44, 44)
    pygame.draw.rect(c, CELL, ic, border_radius=3)
    pygame.draw.rect(c, GOLD, ic, 1, border_radius=3)
    _icon(c, ic.inflate(-6, -6), iid)
    karma_lvl = (p.get("levels") or {}).get("karma", 1)
    nm = item.get("name", iid)
    if slot == "ammo" and iid == "arrow_quiver":
        nm = f"Arrow Quiver  ·  {int(p.get('quiver_total') or 0)} arrows"
    elif slot == "ammo":
        nm = f"{nm}  ×{sum(int(e.get('qty') or 0) for e in inv.values() if e and e.get('item_id') == iid)}"
    x = ic.right + 10
    nr = _text(c, nm, font("title", 17), GOLD_HI, (x, TOOLTIP.y + 4))
    _text(c, _slot_hint(slot), font("body", 13), MUTED, (TOOLTIP.right - 10, TOOLTIP.y + 8), anchor="topright") \
        if nr.right + 12 + font("body", 13).size(_slot_hint(slot))[0] < TOOLTIP.right - 10 else None
    f = font("body", 15)
    y = TOOLTIP.y + 31
    if slot == "ammo":
        best = ITEMS.get(p.get("quiver_best")) or item
        line = [(f"Ranged +{best.get('ranged_att', 0)} att / +{best.get('ranged_str', 0)} str", TEXT)]
    else:
        kb = karma_slot_bonus(slot, karma_lvl)
        line = []
        for lab, k in (("Att", "att_bonus"), ("Str", "str_bonus"), ("Def", "def_bonus")):
            line.append((f"{lab} +{item.get(k, 0)}", TEXT))
            if kb.get(k):
                line.append((f"(+{kb[k]}k)", GAIN_TXT))
            line.append(("   ", TEXT))
        from content import weapon_stats
        ws = weapon_stats(iid) if slot == "weapon" else None
        if ws:
            line.append((f"Speed {ws['attack_speed']}  Crit {round(ws['crit_chance'] * 100)}%", WEAPON_C))
    for txt, col in line:
        r = _text(c, txt, f, col, (x, y))
        x = r.right + (3 if txt.strip() else 0)


def _draw_right(client, c, ITEMS, karma_slot_bonus, dx=0, dy=0):
    p = client.player or {}
    eq = p.get("equipment") or {}
    levels = p.get("levels") or {}
    wb = _bonuses(client, ITEMS, karma_slot_bonus)
    kb_tot = p.get("karma_bonuses") or {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    pot = p.get("stat_boosts") or {}
    M = lambda r: r.move(dx, dy)
    _panel(c, M(RIGHT_PANEL), 31)
    x0 = 468 + dx
    _text(c, "Worn bonuses", font("title", 18), TITLE_GOLD, (x0, 74 + dy))
    rows = (("Attack", "att_bonus", ATT_C, "att"), ("Strength", "str_bonus", STR_C, "str"),
            ("Defence", "def_bonus", DEF_C, "def"))
    for (lab, key, col, g), ry in zip(rows, BONUS_ROWS_Y):
        card = pygame.Rect(x0, ry + dy, 400, 40)
        pygame.draw.rect(c, ROW, card, border_radius=3)
        pygame.draw.rect(c, ROW_RIM, card, 1, border_radius=3)
        _glyph(c, g, card.x + 20, card.centery, col)
        _text(c, lab, font("body", 17), TEXT, (card.x + 42, card.y + 1))
        _text(c, f"karma +{int(kb_tot.get(key, 0) or 0)}", font("body", 13), MUTED, (card.x + 42, card.y + 21))
        val = int(wb.get(key, 0) or 0)
        shown, delta, age = _anim_value(client, key, val)
        _seg_bar(c, card.x + 150, card.centery - 3, shown, col)
        vr = _text(c, f"+{shown}", font("bold", 18), col, (card.right - 10, card.centery), anchor="midright")
        if delta:
            dcol = GAIN_TXT if delta > 0 else LOSS_TXT
            _text(c, f"{'+' if delta > 0 else '-'}{abs(delta)}", font("bold", 14), dcol,
                  (vr.x - 6, card.centery), anchor="midright")
    ra, rsb = int(wb.get("ranged_att", 0) or 0), int(wb.get("ranged_str", 0) or 0)
    card = pygame.Rect(x0, BONUS_ROWS_Y[3] + dy, 400, 40)
    pygame.draw.rect(c, ROW, card, border_radius=3)
    pygame.draw.rect(c, ROW_RIM, card, 1, border_radius=3)
    _glyph(c, "rng", card.x + 22, card.centery, RNG_C)
    _text(c, f"Ranged   +{ra} att  /  +{rsb} str", font("body", 17), TEXT, (card.x + 42, card.centery), anchor="midleft")
    fill = min(1.0, (ra + rsb) / 60.0)
    bar = pygame.Rect(card.x + 268, card.centery - 3, 120, 6)
    pygame.draw.rect(c, (RNG_C[0] // 4, RNG_C[1] // 4, RNG_C[2] // 4), bar)
    pygame.draw.rect(c, RNG_C, (bar.x, bar.y, int(bar.w * fill), bar.h))

    _text(c, "Combat levels", font("title", 18), TITLE_GOLD, (x0, 286 + dy))

    def combat(label, skill, gear_key):
        base = int(levels.get(skill, 1))
        amt = int((pot.get(skill) or {}).get("amount") or 0)
        gear = int(wb.get(gear_key, 0) or 0)
        if amt > 0:
            return label, str(base + amt), f"base {base}  pot +{amt}  gear +{gear}"
        return label, str(base), f"gear +{gear}"
    tiles = [combat("Attack", "attack", "att_bonus"), combat("Strength", "strength", "str_bonus"),
             combat("Defence", "defence", "def_bonus"),
             ("Archery", str(int(levels.get("archery", 1))), f"ranged +{ra} att / +{rsb} str")]
    for (lab, val, sub), (tx, ty) in zip(tiles, LEVEL_TILES):
        t = pygame.Rect(tx + dx, ty + dy, 196, 46)
        pygame.draw.rect(c, TILE, t, border_radius=3)
        pygame.draw.rect(c, PANEL_RIM, t, 1, border_radius=3)
        _text(c, lab, font("body", 17), TEXT, (t.x + 10, t.y + 2))
        _text(c, val, font("bold", 19), FLASH, (t.right - 10, t.y + 3), anchor="topright")
        _text(c, sub, font("body", 13), MUTED, (t.x + 10, t.y + 25))
    hp = M(HP_RECT)
    pygame.draw.rect(c, TILE, hp, border_radius=3)
    pygame.draw.rect(c, PANEL_RIM, hp, 1, border_radius=3)
    cur, mx = int(p.get("hp") or 0), max(1, int(p.get("max_hp") or 1))
    _text(c, "Hitpoints", font("body", 17), TEXT, (hp.x + 10, hp.y + 1))
    _text(c, "top 3 combat skills", font("body", 13), MUTED, (hp.x + 10, hp.y + 21))
    _text(c, f"{cur}/{mx}", font("bold", 19), FLASH if cur * 4 >= mx else LOSS_TXT, (hp.right - 10, hp.centery), anchor="midright")
    info = M(INFO_RECT)
    pygame.draw.line(c, (GOLD[0] // 2, GOLD[1] // 2, GOLD[2] // 2), (info.x, info.y - 4), (info.right, info.y - 4), 1)
    y = info.y
    kr = _text(c, f"Karma {levels.get('karma', 1)}", font("body", 19), KARMA_C, (info.x, y))
    _text(c, f"(+{kb_tot.get('att_bonus', 0)}a / +{kb_tot.get('str_bonus', 0)}s / +{kb_tot.get('def_bonus', 0)}d)",
          font("body", 14), MUTED, (kr.right + 10, y + 4))
    y += 22
    _text(c, f"Combat {client.player_combat_level()}   ·   Total {client.player_total_level()}",
          font("body", 18), COMBAT_C, (info.x, y))
    y += 22
    import eclipse_fx
    from content import ITEMS, bow_attack_range, is_bow, weapon_stats
    wid = eq.get("weapon")
    ws = weapon_stats(wid) if wid else None
    if ws:
        wline = (f"Weapon: Speed {ws['attack_speed']} · Crit {round(ws['crit_chance'] * 100)}% · "
                 f"Heavy +{round(ws['heavy_bonus'] * 100)}%")
    elif wid and is_bow(wid):
        name = (ITEMS.get(wid) or {}).get("name", "Bow")
        wline = f"Weapon: {name} · Range {bow_attack_range(wid)} · shoots arrows"
    else:
        wline = "Weapon: no sword, axe, or bow"
    _text(c, wline, font("body", 14), WEAPON_C, (info.x, y))
    y += 18
    tier = eclipse_fx.fx_tier(eq)
    if tier:
        name, how = eclipse_fx.TIER_LABELS.get(tier, (tier.title(), ""))
        pygame.draw.circle(c, FLASH, (info.x + 6, y + 8), 5)
        _text(c, f"Set glow: {name} ({how})", font("body", 14), TEXT, (info.x + 16, y))
    else:
        pygame.draw.circle(c, MUTED, (info.x + 6, y + 8), 4, 1)
        _text(c, "Set glow: none (full Mithril, Adamantite or Mythos set)", font("body", 14), MUTED, (info.x + 16, y))


def _seg_bar(c, x, y, val, col):
    dim = (col[0] // 4 + 8, col[1] // 4 + 6, col[2] // 4 + 6)
    for i in range(10):
        seg = pygame.Rect(x + i * 13, y, 10, 6)
        fill = max(0.0, min(1.0, (val - i * 50) / 50.0))
        pygame.draw.rect(c, dim, seg)
        if fill > 0:
            pygame.draw.rect(c, col, (seg.x, seg.y, max(1, int(seg.w * fill)), seg.h))


def _draw_footer(c, y, w):
    pygame.draw.line(c, (GOLD[0] * 2 // 5, GOLD[1] * 2 // 5, GOLD[2] * 2 // 5), (24, y - 2), (w - 24, y - 2), 1)
    f = font("body", 15)
    txt = FOOTER if f.size(FOOTER)[0] < w - 40 else "Click item to equip · click slot to unequip · Esc / E"
    img = f.render(txt, True, TITLE_GOLD)
    img.set_alpha(217)
    c.blit(img, img.get_rect(center=(w // 2, y + 12)))


_VIGNETTE = {}
# Soft backdrop only — old values (0.62–0.82) made the inventory sidebar unreadable
# during the equip tutorial and inside the sewer.
_VIGNETTE_CENTER = 0.22
_VIGNETTE_EDGE = 0.38


def _vignette(size, clear_sidebar=None):
    """Dark wash behind the equipment window. Optional clear_sidebar keeps the HUD bag readable."""
    key = (size, clear_sidebar)
    if key not in _VIGNETTE:
        w, h = size
        small = pygame.Surface((64, 48), pygame.SRCALPHA)
        for yy in range(48):
            for xx in range(64):
                d = math.hypot((xx - 31.5) / 32, (yy - 23.5) / 24) / 1.414
                a = int(255 * min(
                    _VIGNETTE_EDGE,
                    _VIGNETTE_CENTER + (_VIGNETTE_EDGE - _VIGNETTE_CENTER) * max(0.0, d - 0.25) / 0.75,
                ))
                small.set_at((xx, yy), (*OVERLAY, a))
        vig = pygame.transform.smoothscale(small, (w, h))
        if clear_sidebar is not None and 0 < clear_sidebar < w:
            # Punch out the inventory sidebar so armour in the bag stays bright.
            vig.fill((0, 0, 0, 0), pygame.Rect(clear_sidebar, 0, w - clear_sidebar, h))
        _VIGNETTE[key] = vig
    return _VIGNETTE[key]


def _safe(where, fn, *a, **k):
    """Draw one section; on failure log it and keep drawing the rest (the panel is never left half-drawn)."""
    try:
        return fn(*a, **k)
    except Exception as e:
        _log_once(where, e)
        return None


def draw(self, ITEMS, karma_slot_bonus, sprites=None, weapon_style=None):
    scr = self.screen
    vp = viewport(self)
    # Soft wash over the world only — keep the inventory sidebar undimmed so armour
    # stays readable during the equip tutorial and inside the rat sewer.
    clear_x = vp.right if vp.right < scr.get_width() else None
    scr.blit(_vignette(scr.get_size(), clear_sidebar=clear_x), (0, 0))
    L = layout(vp.w, vp.h)
    L["vp"] = vp
    self._equip_layout = L
    cw, ch = L["canvas"]
    canvas = self.__dict__.get("_equip_canvas")
    if canvas is None or canvas.get_size() != (cw, ch):
        canvas = _opaque(cw, ch)
        self._equip_canvas = canvas
    canvas.fill(WINDOW_BG)                       # never show a stale / see-through canvas
    _safe("frame", _draw_frame, canvas, cw, ch)
    mx, my = pygame.mouse.get_pos()
    m = _to_logical(self, mx, my)
    eq = (self.player or {}).get("equipment") or {}
    _detect_changes(self, eq)
    if L["mode"] == "full":
        _safe("title", _draw_title, self, canvas)
        _safe("equip_all", _draw_equip_all, self, canvas, m)
        _safe("left", _draw_left, self, canvas, ITEMS, karma_slot_bonus, m)
        _safe("right", _draw_right, self, canvas, ITEMS, karma_slot_bonus)
        _safe("footer", _draw_footer, canvas, FOOTER_Y, cw)
        # carved divider between the panels
        dx = (LEFT_PANEL.right + RIGHT_PANEL.x) // 2
        pygame.draw.line(canvas, WOOD_DK, (dx, LEFT_PANEL.y + 10), (dx, LEFT_PANEL.bottom - 10), 3)
        pygame.draw.line(canvas, WOOD_HI, (dx + 2, LEFT_PANEL.y + 10), (dx + 2, LEFT_PANEL.bottom - 10), 1)
        _diamond(canvas, dx, LEFT_PANEL.centery, 6, GOLD)
        _diamond(canvas, dx, LEFT_PANEL.centery, 2, GOLD_HI)
        scroll = 0
    else:
        _safe("title", _draw_title, self, canvas, name_rect=pygame.Rect(16, STACK_DY + 8, STACK_W - 36, 24))
        _safe("equip_all", _draw_equip_all, self, canvas, m)
        _safe("left", _draw_left, self, canvas, ITEMS, karma_slot_bonus, m)
        _safe("right", _draw_right, self, canvas, ITEMS, karma_slot_bonus, dx=-_RIGHT_DX, dy=STACK_DY - RIGHT_PANEL.y + 30)
        _safe("footer", _draw_footer, canvas, STACK_H - 30, cw)
        vis_h = int(L["h"] / L["scale"])
        self.equip_scroll = max(0, min(int(getattr(self, "equip_scroll", 0) or 0), ch - vis_h))
        scroll = self.equip_scroll
    s = L["scale"]
    src = canvas.subsurface(pygame.Rect(0, scroll, cw, min(ch - scroll, int(round(L["h"] / s)))))
    shadow = pygame.Rect(vp.x + L["ox"], vp.y + L["oy"], L["w"], L["h"])
    sh = pygame.Surface((shadow.w + 40, shadow.h + 40), pygame.SRCALPHA)
    for i in range(20):
        pygame.draw.rect(sh, (0, 0, 0, 9), sh.get_rect().inflate(-i * 2, -i * 2), border_radius=12)
    scr.blit(sh, (shadow.x - 20, shadow.y - 8))
    if s == 1.0:
        scr.blit(src, shadow.topleft)
    else:
        scr.blit(pygame.transform.smoothscale(src, (L["w"], L["h"])), shadow.topleft)
    # screen-space rects (same keys as before: click a filled slot = UNEQUIP)
    self.equip_slot_rects = {k: _screen_rect(L, r, scroll) for k, r in slot_rects().items()}
    self.equip_all_rect = _screen_rect(L, EQUIP_ALL_RECT, scroll)
    _draw_inventory_flash(self)


def _detect_changes(client, eq):
    """Flash (and clank, unless the click already did) every slot whose item changed."""
    now = time.time()
    snap = {k: eq.get(k) for k in SLOTS}
    prev = client.__dict__.get("_equip_prev")
    last = client.__dict__.get("_equip_prev_t", 0.0)
    if prev is not None and now - last < 0.6:
        changed = [k for k in SLOTS if prev.get(k) != snap.get(k)]
        if changed:
            fl = client.__dict__.setdefault("_equip_flash", {})
            for k in changed:
                fl[k] = now
            if now - client.__dict__.get("_equip_clank_t", 0.0) > 0.8:
                client._equip_clank_t = now
                play_clank()
            client._equip_changes = client.__dict__.get("_equip_changes", 0) + 1
    client._equip_prev = snap
    client._equip_prev_t = now


def _draw_inventory_flash(client):
    f = client.__dict__.get("_equip_inv_flash")
    if not f:
        return
    rect, t0 = f
    a = 1 - (time.time() - t0) / FLASH_S
    if a <= 0:
        client._equip_inv_flash = None
        return
    fl = pygame.Surface((rect.w + 12, rect.h + 12), pygame.SRCALPHA)
    pygame.draw.rect(fl, (*FLASH, int(120 * a)), fl.get_rect().inflate(-6, -6), border_radius=5)
    for i in range(6):
        pygame.draw.rect(fl, (*FLASH, int(220 * a * (1 - i / 6))), fl.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=6)
    client.screen.blit(fl, (rect.x - 6, rect.y - 6))


def flash_slot(client, slot):
    client.__dict__.setdefault("_equip_flash", {})[slot] = time.time()
    client._equip_clank_t = time.time()
    play_clank()


# ---------------------------------------------------------------- input
def handle_click(client, mx, my, ITEMS):
    """One click: inventory item -> EQUIP (server swaps), filled slot -> UNEQUIP. Returns 'equip', 'unequip',
    'inside', or 'outside' (the caller closes the window on 'outside')."""
    p = client.player or {}
    eq = p.get("equipment") or {}
    # Sidebar stays undimmed beside this window — bag cells equip here; every
    # other HUD control (filters / Equipment / Skills / …) must fall through.
    side_x = viewport(client).right
    on_sidebar = side_x < client.screen.get_width() and mx >= side_x
    # 1) inventory cell (the bag stays visible beside the window)
    try:
        cells = client.inventory_slot_rects()
    except Exception:
        cells = {}
    for idx, rect in (cells or {}).items():
        if rect.collidepoint(mx, my) and not window_rect(client).collidepoint(mx, my):
            inv = p.get("inventory") or {}
            entry = inv.get(str(idx)) or inv.get(idx)
            if not entry:
                return "inside"
            item = ITEMS.get(entry.get("item_id")) or {}
            es = item.get("equip_slot")
            if not es:
                client.add_chat(f"You can't wear the {item.get('name', 'item')}.")
                return "inside"
            client.net.send("EQUIP", slot_index=idx)
            target = f"tool_{item.get('tool_for')}" if es == "tool" else es
            if target in SLOTS:
                flash_slot(client, target)
            else:
                play_clank()
            client._equip_inv_flash = (rect.copy(), time.time())
            return "equip"
    if on_sidebar:
        return "outside"
    m = _to_logical(client, mx, my)
    if m is None:
        return "outside"
    if EQUIP_ALL_RECT.collidepoint(m):
        # the server fills every empty slot from the bag (each piece is a normal, validated EQUIP)
        client.net.send("EQUIP_ALL")
        client._equip_all_flash = time.time()
        play_clank()
        return "equip_all"
    for slot, r in slot_rects().items():
        if r.collidepoint(m):
            if eq.get(slot) and slot in LIVE_SLOTS:
                client.net.send("UNEQUIP", equip_slot=slot)
                flash_slot(client, slot)
                return "unequip"
            return "inside"
    return "inside"


def handle_wheel(client, dy):
    L = getattr(client, "_equip_layout", None)
    if not L or L["mode"] != "stack":
        return False
    client.equip_scroll = max(0, int(getattr(client, "equip_scroll", 0) or 0) - int(dy * 60))
    return True
