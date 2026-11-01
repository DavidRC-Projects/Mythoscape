"""Shared Crownfall confirm modal (CONFIRM_MODAL_STYLE_SPEC.md).

draw(client, spec) paints the modal and returns {role: Rect} (+ "box", "close", "dont_ask").
spec = {title, item_id, count, name, note, lines:[(text, colour_key)], helper,
        buttons:[{role: cancel|secondary|primary, label, key}], destructive, dont_ask: label|None,
        dont_ask_on: bool, t0: open time (ms), focus: index}
Callers keep their own click handlers; key()/ready() give Enter/Esc/Tab/1 + the 150ms debounce.
"""
from __future__ import annotations

import json
import math
import os
import random

import pygame

def _c(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

P = {k: _c(v) for k, v in {
    "wood": "#2A1E14", "outline": "#120C08", "bevel": "#5A4630", "gold": "#B39465", "hair": "#E6CB8E",
    "stud": "#CEAE73", "leather": "#4B4233", "plaque": "#1C150F", "slot": "#281F18", "slot_in": "#3A2E22",
    "name": "#E6CB8E", "note": "#CAAE87", "gain": "#7FBF6A", "total": "#FFD36B", "loss": "#C2453B",
    "help": "#A8987A", "hint": "#7A6C55", "glow": "#F2C14E", "title": "#CEAE73"}.items()}
BTN = {
    "primary": ("#E6CB8E", "#9C7A44", "#FFD36B", "#2B2118"),
    "secondary": ("#5A4630", "#2A1E14", "#B39465", "#E6CB8E"),
    "cancel": ("#3A2E22", "#241A12", "#5A4630", "#A8987A"),
    "destructive": ("#9E2B25", "#5E1814", "#E6CB8E", "#F3E6C8"),
}
DEBOUNCE_MS = 150
OPEN_MS = 120
_FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))
_FONTS = {}
_CACHE = {}
_PREFS = os.path.join(os.path.expanduser("~"), ".crownfall", "confirm_prefs.json")


def font(kind, size):
    key = (kind, size)
    if key not in _FONTS:
        name = "Cinzel.ttf" if kind in ("title", "btn") else "EBGaramond.ttf"
        try:
            f = pygame.font.Font(os.path.join(_FONT_DIR, name), size)
        except Exception:
            f = pygame.font.Font(None, size + 4)
        if kind in ("title", "btn", "bold"):
            f.set_bold(True)
        _FONTS[key] = f
    return _FONTS[key]


# ---------------------------------------------------------------- don't-ask-again prefs
def _load_prefs():
    try:
        with open(_PREFS) as fh:
            return json.load(fh)
    except Exception:
        return {}


def skip(key):
    return bool(_load_prefs().get(f"skip_{key}"))


def set_skip(key, on):
    prefs = _load_prefs()
    prefs[f"skip_{key}"] = bool(on)
    try:
        os.makedirs(os.path.dirname(_PREFS), exist_ok=True)
        with open(_PREFS, "w") as fh:
            json.dump(prefs, fh)
    except Exception as e:
        print("[confirm_modal] prefs save failed:", e)


# ---------------------------------------------------------------- timing / keys
def now():
    return pygame.time.get_ticks()


def ready(spec):
    return now() - int(spec.get("t0") or 0) >= DEBOUNCE_MS


def key(spec, event):
    """Return the role a key press picks (primary/secondary/cancel), 'tab', or None."""
    k = event.key
    if k == pygame.K_ESCAPE:
        return "cancel"
    if not ready(spec):
        return None
    if k == pygame.K_TAB:
        n = len(spec.get("buttons") or [])
        f = spec.get("focus")
        spec["focus"] = ((n - 1 if f is None else int(f)) + 1) % max(1, n)
        return "tab"
    if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
        if spec.get("destructive"):
            return None                      # destructive: click only
        btns = spec.get("buttons") or []
        f = spec.get("focus")
        if f is not None and 0 <= f < len(btns):
            return btns[f]["role"]
        return "primary"
    if k in (pygame.K_1, pygame.K_KP1) and any(b["role"] == "secondary" for b in spec.get("buttons") or []):
        return "secondary"
    return None


# ---------------------------------------------------------------- painting helpers
def _grad(w, h, top, bot):
    key = ("g", w, h, top, bot)
    if key not in _CACHE:
        s = pygame.Surface((w, h))
        for i in range(h):
            t = i / max(1, h - 1)
            s.fill(tuple(int(top[j] * (1 - t) + bot[j] * t) for j in range(3)), (0, i, w, 1))
        _CACHE[key] = s
    return _CACHE[key]


def _leather(w, h):
    key = ("lea", w, h)
    if key in _CACHE:
        return _CACHE[key]
    rng = random.Random(3)
    base = P["leather"]
    s = pygame.Surface((w, h))
    s.fill((base[0] - 16, base[1] - 14, base[2] - 10))
    for _ in range(w * h // 18):
        x, y = rng.randrange(w), rng.randrange(h)
        n = rng.randint(-12, 12) + int(6 * math.sin(x / 37 + y / 53))
        c = tuple(max(0, min(255, base[j] - 16 + n)) for j in range(3))
        s.fill(c, (x, y, 2, 2))
    # inner vignette toward #2A2118
    vig = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(24):
        a = int(150 * (1 - i / 24) ** 2)
        pygame.draw.rect(vig, (30, 22, 16, a), (i, i, w - 2 * i, h - 2 * i), 1, border_radius=8)
    s.blit(vig, (0, 0))
    _CACHE[key] = s
    return s


def _text(surf, txt, f, col, pos, anchor="topleft", shadow=True):
    img = f.render(txt, True, col)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(f.render(txt, True, (0, 0, 0)), r.move(1, 2))
    surf.blit(img, r)
    return r


def _diamond(surf, cx, cy, r, fill, edge=None):
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(surf, fill, pts)
    if edge:
        pygame.draw.polygon(surf, edge, pts, 1)


def _corner(surf, cx, cy, sx, sy):
    pts = [(cx, cy), (cx + sx * 46, cy), (cx + sx * 36, cy + sy * 6), (cx + sx * 6, cy + sy * 6),
           (cx + sx * 6, cy + sy * 36), (cx, cy + sy * 46)]
    pygame.draw.polygon(surf, P["gold"], pts)
    pygame.draw.polygon(surf, P["outline"], pts, 1)
    pygame.draw.line(surf, P["hair"], (cx + sx * 3, cy + sy * 3), (cx + sx * 40, cy + sy * 3))
    pygame.draw.line(surf, P["hair"], (cx + sx * 3, cy + sy * 3), (cx + sx * 3, cy + sy * 40))
    ccx, ccy = cx + sx * 14, cy + sy * 14
    _diamond(surf, ccx, ccy, 9, P["stud"], P["outline"])
    pygame.draw.circle(surf, (140, 90, 43), (ccx, ccy), 3)


def _glow(surf, rect, col, rad=8, alpha=100):
    g = pygame.Surface((rect.w + rad * 2, rect.h + rad * 2), pygame.SRCALPHA)
    for i in range(rad, 0, -1):
        a = int(alpha * (1 - i / rad) ** 1.5)
        pygame.draw.rect(g, (*col, a), (rad - i, rad - i, rect.w + 2 * i, rect.h + 2 * i), 2, border_radius=8 + i)
    surf.blit(g, (rect.x - rad, rect.y - rad))


def _button(surf, rect, role, label, hover=False, focus=False, pressed=False, disabled=False, t=0.0):
    top, bot, rim, txt = (_c(h) for h in BTN[role])
    if hover and not disabled:
        top, bot = (tuple(min(255, int(v * 1.1)) for v in top), tuple(min(255, int(v * 1.1)) for v in bot))
        rim = P["hair"]
        _glow(surf, rect, P["glow"], 8, 100)
    if disabled:
        grey = lambda c: tuple(int(c[j] * 0.6 + sum(c) / 3 * 0.4) for j in range(3))
        top, bot, rim, txt = grey(top), grey(bot), grey(rim), _c("#6E665C")
    r = rect.move(0, 2) if pressed else rect
    if pressed:
        top, bot = tuple(int(v * 0.92) for v in bot), tuple(int(v * 0.92) for v in top)
    sh = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, 170), (0, 0, r.w, r.h), border_radius=7)
    surf.blit(sh, (r.x + 2, r.y + (1 if pressed else 4)))
    g = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    g.blit(_grad(r.w, r.h, top, bot), (0, 0))
    m = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, r.w, r.h), border_radius=7)
    g.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(g, r.topleft)
    pygame.draw.rect(surf, rim, r, 2, border_radius=7)
    pygame.draw.line(surf, tuple(min(255, v + 60) for v in top), (r.x + 8, r.y + 3), (r.right - 9, r.y + 3))
    if focus:
        a = int(140 + 115 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.2)))
        fr = pygame.Surface((r.w + 8, r.h + 8), pygame.SRCALPHA)
        pygame.draw.rect(fr, (*P["total"], a), (0, 0, r.w + 8, r.h + 8), 2, border_radius=10)
        surf.blit(fr, (r.x - 4, r.y - 4))
    f = font("btn", 18 if role != "cancel" else 16)
    while f.size(label)[0] > r.w - 14 and f.get_height() > 12:
        f = font("btn", f.get_height() - 3)
    _text(surf, label, f, txt, r.center, "center")


def _icon(surf, rect, item_id, count, flash=0.0):
    pygame.draw.rect(surf, P["outline"], rect.inflate(8, 8), border_radius=10)
    pygame.draw.rect(surf, P["gold"], rect.inflate(8, 8), 3, border_radius=10)
    pygame.draw.rect(surf, P["slot"], rect.inflate(-4, -4), border_radius=7)
    pygame.draw.rect(surf, P["slot_in"], rect.inflate(-4, -4), 1, border_radius=7)
    gl = pygame.Surface(rect.size, pygame.SRCALPHA)
    for i in range(18):
        pygame.draw.circle(gl, (*P["stud"], 4), (rect.w // 2, rect.h // 2), rect.w // 2 - 6 - i)
    surf.blit(gl, rect.topleft)
    drawn = False
    if item_id:
        try:
            import realistic_item_icons
            drawn = realistic_item_icons.draw_icon(surf, rect.inflate(-6, -6), item_id)
        except Exception as e:
            print("[confirm_modal] icon fallback:", e)
    if not drawn:  # plain gold rune so the slot is never empty
        _diamond(surf, rect.centerx, rect.centery, 22, P["gold"], P["outline"])
    if flash > 0:
        fl = pygame.Surface(rect.size, pygame.SRCALPHA)
        fl.fill((*P["total"], int(170 * flash)))
        surf.blit(fl, rect.topleft)
    if count and count > 1:
        bf = font("bold", 17)
        label = f"x{count}"
        w = max(40, bf.size(label)[0] + 18)
        b = pygame.Rect(rect.right - w + 6, rect.bottom - 22, w, 24)
        pygame.draw.rect(surf, P["plaque"], b, border_radius=8)
        pygame.draw.rect(surf, P["hair"], b, 2, border_radius=8)
        _text(surf, label, bf, P["total"], b.center, "center", shadow=False)


def _backdrop(screen):
    w, h = screen.get_size()
    small = pygame.transform.smoothscale(screen, (max(1, w // 10), max(1, h // 10)))
    small = pygame.transform.smoothscale(small, (max(1, w // 5), max(1, h // 5)))
    blur = pygame.transform.smoothscale(small, (w, h))
    dark = pygame.Surface((w, h), pygame.SRCALPHA)
    dark.fill((2, 3, 5, 150))
    blur.blit(dark, (0, 0))
    key = ("vig", w, h)
    if key not in _CACHE:
        v = pygame.Surface((w // 4 + 1, h // 4 + 1), pygame.SRCALPHA)
        vw, vh = v.get_size()
        for y in range(vh):
            for x in range(vw):
                d = math.hypot((x - vw / 2) / (vw / 2), (y - vh / 2) / (vh / 2))
                v.set_at((x, y), (2, 3, 5, int(max(0, min(1, (d - 0.55) / 0.7)) * 170)))
        _CACHE[key] = pygame.transform.smoothscale(v, (w, h))
    blur.blit(_CACHE[key], (0, 0))
    screen.blit(blur, (0, 0))


# ---------------------------------------------------------------- main draw
def draw(client, spec, screen=None):
    screen = screen or client.screen
    sw, sh = screen.get_size()
    t_ms = now() - int(spec.get("t0") or 0)
    k = min(1.0, max(0.0, t_ms / OPEN_MS))
    ease = 1 - (1 - k) ** 3
    _backdrop(screen) if ease >= 1 else _fade_backdrop(screen, ease)

    lines = spec.get("lines") or []
    has_cb = bool(spec.get("dont_ask"))
    W = 560
    text_h = 50 + 26 * len(lines) + (20 if spec.get("helper") else 0)
    body_h = max(104, text_h)
    H = 26 + 44 + body_h + (30 if has_cb else 8) + 46 + 22 + 26
    H = min(420, max(300, H))
    scale = min(1.0, (sw - 48) / W, (sh - 48 - 24) / (H + 20))
    scale = max(0.8, scale) * (0.94 + 0.06 * ease)

    surf = pygame.Surface((W + 80, H + 80), pygame.SRCALPHA)
    ox, oy = 40, 40
    box = pygame.Rect(ox, oy, W, H)
    # drop shadow
    shd = pygame.Surface((W + 80, H + 80), pygame.SRCALPHA)
    for i in range(14, 0, -1):
        pygame.draw.rect(shd, (0, 0, 0, int(14 * (1 - i / 14) + 4)), box.move(0, 12).inflate(i * 3, i * 3), border_radius=14 + i)
    surf.blit(shd, (0, 0))
    pygame.draw.rect(surf, P["wood"], box, border_radius=12)
    pygame.draw.rect(surf, P["outline"], box, 2, border_radius=12)
    pygame.draw.line(surf, P["bevel"], (box.x + 4, box.y + 3), (box.right - 7, box.y + 3), 2)
    pygame.draw.line(surf, P["bevel"], (box.x + 3, box.y + 4), (box.x + 3, box.bottom - 7), 2)
    inner = box.inflate(-28, -28)
    surf.blit(_leather(inner.w, inner.h), inner.topleft)
    pygame.draw.rect(surf, P["gold"], box.inflate(-16, -16), 3, border_radius=8)
    pygame.draw.rect(surf, P["hair"], box.inflate(-24, -24), 1, border_radius=6)
    for cx, cy, sx, sy in ((box.x + 2, box.y + 2, 1, 1), (box.right - 3, box.y + 2, -1, 1),
                           (box.x + 2, box.bottom - 3, 1, -1), (box.right - 3, box.bottom - 3, -1, -1)):
        _corner(surf, cx, cy, sx, sy)

    rects = {}
    mx, my = _mouse_local(client, screen, scale, W, H, sw, sh, ox, oy)
    # banner
    tf = font("title", 26)
    title = str(spec.get("title") or "CONFIRM?").upper()
    tw = tf.size(title)[0] + 60
    bx0, bx1 = box.centerx - tw // 2, box.centerx + tw // 2
    by0, by1 = box.y - 20, box.y + 26
    mid = (by0 + by1) // 2
    pts = [(bx0 - 18, mid), (bx0, by0), (bx1, by0), (bx1 + 18, mid), (bx1, by1), (bx0, by1)]
    pygame.draw.polygon(surf, P["plaque"], pts)
    pygame.draw.polygon(surf, P["gold"], pts, 2)
    pts2 = [(bx0 - 11, mid), (bx0 + 3, by0 + 4), (bx1 - 3, by0 + 4), (bx1 + 11, mid), (bx1 - 3, by1 - 4), (bx0 + 3, by1 - 4)]
    pygame.draw.polygon(surf, P["bevel"], pts2, 1)
    _text(surf, title, tf, P["title"], (box.centerx, mid + 1), "center")
    # close X (drawn as lines)
    cc = (box.right - 34, box.y + 38)
    close = pygame.Rect(cc[0] - 13, cc[1] - 13, 26, 26)
    hov = close.collidepoint(mx, my)
    if hov:
        pygame.draw.circle(surf, (*P["glow"], 90), cc, 17)
    pygame.draw.circle(surf, P["slot"], cc, 13)
    pygame.draw.circle(surf, P["hair"] if hov else P["gold"], cc, 13, 2)
    for a, b in (((-5, -5), (5, 5)), ((-5, 5), (5, -5))):
        pygame.draw.line(surf, P["hair"], (cc[0] + a[0], cc[1] + a[1]), (cc[0] + b[0], cc[1] + b[1]), 3)
    rects["close"] = close
    # icon slot
    S = 96
    slot = pygame.Rect(box.x + 40, box.y + 64, S, S)
    flash = max(0.0, 1 - (now() - spec["flash_t"]) / 200) if spec.get("flash_t") else 0.0
    _icon(surf, slot, spec.get("item_id"), int(spec.get("count") or 1), flash)
    # text block
    tx = slot.right + 28
    nf = font("title", 24)
    nr = _text(surf, str(spec.get("name") or ""), nf, P["name"], (tx, box.y + 62))
    if spec.get("note"):
        _text(surf, spec["note"], font("serif", 17), P["note"], (nr.right + 10, nr.bottom - 4), "bottomleft", False)
    dy = box.y + 104
    pygame.draw.line(surf, P["bevel"], (tx, dy), (box.right - 40, dy))
    _diamond(surf, tx + 150, dy, 4, P["gold"])
    y = dy + 12
    for txt, ck in lines:
        if ck == "coin":
            pygame.draw.circle(surf, (120, 86, 30), (tx + 8, y + 11), 8)
            pygame.draw.circle(surf, P["total"], (tx + 8, y + 10), 7)
            pygame.draw.circle(surf, (156, 122, 68), (tx + 8, y + 10), 4, 1)
            _text(surf, txt, font("bold", 19), P["total"], (tx + 22, y))
        else:
            _text(surf, txt, font("bold", 19), P.get(ck, P["note"]), (tx, y))
        y += 26
    if spec.get("helper"):
        _text(surf, spec["helper"], font("serif", 15), P["help"], (tx, y), shadow=False)
    # don't ask again
    by = box.bottom - 26 - 22 - 46
    if has_cb:
        cb = pygame.Rect(box.x + 44, by - 30, 16, 16)
        pygame.draw.rect(surf, P["slot"], cb)
        pygame.draw.rect(surf, P["gold"], cb, 2)
        if spec.get("dont_ask_on"):
            pygame.draw.lines(surf, P["total"], False, [(cb.x + 3, cb.y + 8), (cb.x + 7, cb.y + 12), (cb.x + 13, cb.y + 3)], 3)
        lr = _text(surf, spec["dont_ask"], font("serif", 15), P["note"], (cb.right + 10, cb.centery), "midleft", False)
        rects["dont_ask"] = cb.union(lr).inflate(6, 6)
    # buttons: Cancel, Secondary, Primary (primary widest, rightmost)
    btns = spec.get("buttons") or []
    widths = {"cancel": 130, "secondary": 140}
    gap = 14
    avail = W - 80
    fixed = sum(widths.get(b["role"], 0) for b in btns if b["role"] in widths) + gap * (len(btns) - 1)
    x = box.x + 40
    if len(btns) < 3:
        x = box.right - 40 - (fixed + 200)
    tsec = now() / 1000.0
    pressed = spec.get("pressed")
    for i, b in enumerate(btns):
        role = b["role"]
        w = widths.get(role) or max(182, (box.right - 40) - x)
        r = pygame.Rect(x, by, w, 46)
        draw_role = "destructive" if (role == "primary" and spec.get("destructive")) else role
        _button(surf, r, draw_role, b["label"], hover=r.collidepoint(mx, my), focus=(spec.get("focus") == i),
                pressed=(pressed == role), disabled=bool(b.get("disabled")), t=tsec)
        rects[role] = r
        hint = b.get("key")
        if hint is None:
            hint = {"cancel": "Esc", "primary": None if spec.get("destructive") else "Enter",
                    "secondary": "1"}.get(role)
        if hint:
            _keycap(surf, r.centerx, r.bottom + 14, hint)
        x = r.right + gap
    # compose onto screen with open animation
    alpha = int(255 * ease)
    if scale != 1.0:
        surf = pygame.transform.smoothscale(surf, (int(surf.get_width() * scale), int(surf.get_height() * scale)))
    surf.set_alpha(alpha) if alpha < 255 else None
    dst = surf.get_rect(center=(sw // 2, sh // 2 + int(12 * scale)))
    screen.blit(surf, dst)
    out = {"box": _to_screen(box, scale, dst, ox, oy)}
    for kname, r in rects.items():
        out[kname] = _to_screen(r, scale, dst, 0, 0)
    spec["_layout"] = (scale, dst.topleft)
    return out


def _keycap(surf, cx, cy, label):
    f = font("serif", 13)
    w = max(22, f.size(label)[0] + 12)
    r = pygame.Rect(cx - w // 2, cy - 9, w, 18)
    pygame.draw.rect(surf, P["outline"], r.move(0, 2), border_radius=4)
    pygame.draw.rect(surf, P["plaque"], r, border_radius=4)
    pygame.draw.rect(surf, P["bevel"], r, 1, border_radius=4)
    _text(surf, label, f, P["help"], r.center, "center", False)


def _to_screen(r, scale, dst, ox, oy):
    return pygame.Rect(dst.x + int(r.x * scale), dst.y + int(r.y * scale), max(1, int(r.w * scale)), max(1, int(r.h * scale)))


def _mouse_local(client, screen, scale, W, H, sw, sh, ox, oy):
    try:
        mx, my = pygame.mouse.get_pos()
    except Exception:
        return -1, -1
    fw, fh = (W + 80) * scale, (H + 80) * scale
    x0, y0 = sw / 2 - fw / 2, sh / 2 + 12 * scale - fh / 2
    return int((mx - x0) / scale), int((my - y0) / scale)


def _fade_backdrop(screen, ease):
    snap = screen.copy()
    _backdrop(snap)
    snap.set_alpha(int(255 * ease))
    screen.blit(snap, (0, 0))


# ---------------------------------------------------------------- variant builders
def bury_spec(prompt, items):
    item = items.get(prompt.get("item_id")) or {}
    qty = max(1, int(prompt.get("qty") or 1))
    xp = int(item.get("karma_xp") or 0)
    lines = [(f"+{xp} Karma XP each", "gain")]
    if qty > 1:
        lines.append((f"Bury all: +{xp * qty} Karma XP", "total"))
    btns = [{"role": "cancel", "label": "Cancel"}]
    if qty > 1:
        btns += [{"role": "secondary", "label": "Bury 1"}, {"role": "primary", "label": f"Bury all ({qty})"}]
    else:
        btns += [{"role": "primary", "label": "Bury"}]
    stack = item.get("max_stack")
    return {"title": "Bury bones?", "item_id": prompt.get("item_id"), "count": qty,
            "name": prompt.get("name") or item.get("name") or "Bones",
            "note": f"x{qty} in your pack", "lines": lines,
            "helper": f"Stacks to {stack}." if stack else None, "buttons": btns,
            "dont_ask": "Don't ask again for bones", "dont_ask_on": bool(prompt.get("dont_ask_on")),
            "t0": prompt.get("t0") or 0, "focus": prompt.get("focus"), "flash_t": prompt.get("flash_t")}


RARE_TIERS = ("rare", "epic", "legendary", "mythic", "mythos", "crownforged", "eclipse", "dragon")


def is_rare(item_id, item):
    if (item or {}).get("rarity") in RARE_TIERS or (item or {}).get("tier") in RARE_TIERS:
        return True
    return int((item or {}).get("value") or 0) >= 5000


def drop_spec(prompt, items):
    item = items.get(prompt.get("item_id")) or {}
    qty = max(1, int(prompt.get("qty") or 1))
    rare = is_rare(prompt.get("item_id"), item)
    lines = [("Others can pick this up.", "loss")]
    if rare:
        lines.append(("Valuable item: click to confirm.", "loss"))
    btns = [{"role": "cancel", "label": "Cancel"}]
    if qty > 1:
        btns += [{"role": "secondary", "label": "Drop 1"}, {"role": "primary", "label": f"Drop all ({qty})"}]
    else:
        btns += [{"role": "primary", "label": "Drop"}]
    return {"title": "Drop item?", "item_id": prompt.get("item_id"), "count": qty,
            "name": prompt.get("name") or item.get("name") or "Item",
            "note": f"x{qty} in this stack" if qty > 1 else None, "lines": lines,
            "helper": "It lands on the ground at your feet.", "buttons": btns, "destructive": rare,
            "t0": prompt.get("t0") or 0, "focus": prompt.get("focus"), "flash_t": prompt.get("flash_t")}


def sell_spec(name, item_id, qty, price_each, t0=0):
    btns = [{"role": "cancel", "label": "Cancel"}]
    if qty > 1:
        btns += [{"role": "secondary", "label": "Sell 1"}, {"role": "primary", "label": f"Sell all ({qty})"}]
    else:
        btns += [{"role": "primary", "label": "Sell"}]
    return {"title": f"Sell {qty} {name}?" if qty > 1 else f"Sell {name}?", "item_id": item_id, "count": qty,
            "name": name, "lines": [(f"{price_each} coins each", "gain"), (f"+{price_each * qty} coins", "coin")],
            "buttons": btns, "t0": t0}


def dismiss_spec(name, item_id=None, t0=0):
    return {"title": "Dismiss soldier?", "item_id": item_id, "count": 1, "name": name,
            "lines": [("They leave your company for good.", "loss")], "destructive": True,
            "buttons": [{"role": "cancel", "label": "Keep"}, {"role": "primary", "label": "Dismiss"}], "t0": t0}
