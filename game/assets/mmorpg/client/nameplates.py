"""Overhead nameplates & health bars (NAMEPLATES_SPEC.md v1).

One component for players, NPCs, champions, monsters and pets. Call sites in client.py
submit() a plate during the map pass (pre-zoom screen coords). flush() runs after zoom:
sort by feet Y -> push up (max 3) -> collapse to bar -> clamp -> smooth, then draws.
Health bar sits 10 px above the head top (8 px pets); name row 2 px above the bar, so the
name can never cover the bar. All glyphs (stars, ellipsis) are drawn as shapes / ASCII.
"""
from __future__ import annotations

import math
import time

import pygame

def _c(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

ROW_FILL = (20, 15, 12, 214)
RIM, RIM_HOVER, RIM_TARGET = _c("#8A6A3E"), _c("#B39465"), _c("#E6CB8E")
OUTLINE, TROUGH, CHUNK = _c("#0A0806"), _c("#281E16"), _c("#F4EDE0")
FILL = {"friendly": (_c("#4CAF50"), _c("#79DC7D")), "hostile": (_c("#C8372D"), _c("#F5645A")),
        "neutral": (_c("#E0A030"), _c("#FFCD5D"))}
NAME = {"self": _c("#AAE18C"), "party": _c("#8CC8F0"), "hostile": _c("#F07864"),
        "neutral": _c("#F0C878"), "pet": _c("#D2D2C8"), "npc": _c("#F0C878"), "royal": (255, 205, 60)}
BAND_G, BAND_A, BAND_R, CHIP_NEUTRAL = _c("#78C85A"), _c("#E8B03C"), _c("#DC4637"), _c("#C8BEAA")
SIZES = {"std": (96, 10, 16), "mon": (68, 10, 16), "pet": (48, 5, 13)}  # bar w, bar h, name row h

MODE_ALL, MODE_TARGET = "all", "target"
PREFS = {"numbers": "target", "pets": True, "own": True}  # Off/Target/All; Options UI pending
_FONTS = {}
_STATE = {}  # key -> {"pos": (x,y), "shown": hp, "hold": t, "from": hp, "combat": t, "max": m}


def level_band(unit_level, player_level):
    """Shared band (arena thresholds 1.15 / 0.85), read as danger to the player."""
    r = max(1, int(unit_level or 1)) / max(1, int(player_level or 1))
    if r >= 1.15:
        return BAND_R
    if r >= 0.85:
        return BAND_A
    return BAND_G


def _font(size, bold=True):
    key = (size, bold)
    if key not in _FONTS:
        f = pygame.font.SysFont("dejavusans,arial,helvetica", size, bold=bold)
        _FONTS[key] = f
    return _FONTS[key]


def mode(client):
    ov = getattr(client, "np_mode_override", None)
    if ov in (MODE_ALL, MODE_TARGET):
        return ov
    return default_mode(client)


def default_mode(client):
    """Target/hover only in towns, the tavern and the arena lobby; everything elsewhere."""
    try:
        if getattr(client, "dungeon", None):
            d = str(getattr(client, "dungeon", "") or "").lower()
            return MODE_TARGET if ("tavern" in d or "inn" in d or "ox" in d) else MODE_ALL
        import world_map as wm
        px, py = client.player_xy()
        z = str(wm.get_zone(int(px), int(py)) or "")
        if z in ("village", "city", "fishing_village") or "tavern" in z or z == "arena":
            if z == "arena" and (getattr(client, "arena_match", None) or {}).get("active"):
                return MODE_ALL
            return MODE_TARGET
    except Exception:
        pass
    return MODE_ALL


def toggle_mode(client):
    new = MODE_ALL if mode(client) == MODE_TARGET else MODE_TARGET
    client.np_mode_override = new
    try:
        client.add_chat("Nameplates: " + ("show all" if new == MODE_ALL else "target / hover only") + " (V)",
                        color=(230, 203, 142))
    except Exception:
        pass
    return new


def _queue(client):
    q = getattr(client, "_np_queue", None)
    if q is None:
        q = client._np_queue = []
    return q


def submit(client, key, cx, head_top, name, *, level=None, rel="neutral", kind="std", hp=None, max_hp=None,
           stars=None, targeted=False, hovered=False, in_combat=False, feet=None, banner=None,
           name_color=None, show_name=True, owner=None):
    """Queue one plate. head_top = sprite head top Y (not centre). hp None = no bar (NPC)."""
    now = time.time()
    st = _STATE.setdefault(key, {"shown": hp, "hold": 0.0, "from": hp, "combat": 0.0, "pos": None,
                                 "flash": 0.0, "seen": now})
    st["seen"] = now
    if in_combat:
        st["combat"] = now
    if hp is not None and max_hp:
        prev = st.get("shown")
        if prev is None:
            st["shown"] = st["from"] = hp
        elif hp < st.get("last", hp):
            st["from"] = max(st.get("trail_hp", prev), st.get("last", hp))
            st["hold"] = now
        elif hp > st.get("last", hp):
            st["flash"] = now
            st["from"] = hp
        st["last"] = hp
    _queue(client).append({
        "key": key, "cx": float(cx), "head": float(head_top), "name": str(name or ""), "level": level,
        "rel": rel, "kind": kind, "hp": hp, "max": max_hp, "stars": stars, "targeted": targeted,
        "hovered": hovered, "feet": float(feet if feet is not None else head_top + 40), "banner": banner,
        "name_color": name_color, "show_name": show_name, "owner": owner, "in_combat": in_combat,
    })


def _bar_visible(p, st, now):
    if p["hp"] is None or not p["max"]:
        return False
    if p["targeted"] or p["hovered"] or p["in_combat"]:
        return True
    if p["hp"] < p["max"]:
        return True
    return now - st.get("combat", 0) < 4.0


def _trail(st, hp, mx, now):
    """Damage chunk: hold 0.35 s, then shrink to the new value over 0.4 s (ease-out)."""
    src = st.get("from", hp) or hp
    if src <= hp:
        return hp
    dt = now - st.get("hold", 0)
    if dt < 0.35:
        val = src
    elif dt < 0.75:
        u = (dt - 0.35) / 0.4
        u = 1 - (1 - u) ** 3
        val = src + (hp - src) * u
    else:
        val = hp
        st["from"] = hp
    st["trail_hp"] = val
    return val


def _fit(f, s, w):
    if f.size(s)[0] <= w:
        return s
    while s and f.size(s + "...")[0] > w:
        s = s[:-1]
    return s.rstrip() + "..."


def _stroke_text(surf, s, f, col, center=None, midleft=None, alpha=255):
    img = f.render(s, True, col)
    blk = f.render(s, True, (0, 0, 0))
    r = img.get_rect()
    if center:
        r.center = center
    else:
        r.midleft = midleft
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        surf.blit(blk, r.move(ox, oy))
    surf.blit(img, r)
    return r


def _star(surf, cx, cy, r, fill, num):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, OUTLINE, pts, 1)
    _stroke_text(surf, str(num), _font(7), (255, 255, 255), center=(cx, cy + 1))


def _short(n):
    n = int(n)
    return f"{n / 1000:.1f}k" if n > 9999 else str(n)


def _layout(client, p, k, dx, dy):
    bw, bh, nh = SIZES[p["kind"]]
    numeric = _numbers_on(p)
    if p["kind"] == "mon" and not (p["targeted"] or p["hovered"]):
        bh = 6
    if p["kind"] == "std" and not numeric:
        bh = 6
    p["bw"], p["bh"], p["nh"] = bw, bh, nh
    cx = p["cx"] * k + dx
    head = p["head"] * k + dy
    gap = 8 if p["kind"] == "pet" else 10
    bar_bottom = head - gap
    f = _font(9 if p["kind"] == "pet" else 11)
    name = _fit(f, p["name"], 160)
    p["label"] = name
    lvs = str(p["level"]) if p["level"] is not None else None
    lw = (_font(9).size(lvs)[0] + 8) if lvs else 0
    sw = 14 if p["stars"] is not None else 0
    p["lw"], p["sw"] = lw, sw
    pw = int(max(bw, f.size(name)[0] + lw + sw + 14))
    top = bar_bottom - (bh if p["bar"] else 0) - (2 + nh if p["name_on"] else 0)
    if not p["bar"] and not p["name_on"]:
        return None
    rect = pygame.Rect(int(cx - pw / 2), int(top), pw, int(bar_bottom - top))
    return rect


def _numbers_on(p):
    n = PREFS.get("numbers", "target")
    if p["kind"] == "pet" or n == "off":
        return False
    if n == "all":
        return True
    return bool(p["targeted"] or p["rel"] == "self")


def flush(client, k=1.0, dx=0.0, dy=0.0):
    """Lay out + draw every queued unit plate on top of the world (after zoom)."""
    q = list(getattr(client, "_np_queue", None) or [])
    client._np_queue = []
    if not q:
        return []
    now = time.time()
    md = mode(client)
    view = pygame.Rect(0, 0, *client.screen.get_size())
    try:
        import sys
        _cm = sys.modules[type(client).__module__]
        view = pygame.Rect(0, 0, _cm.MAP_W, _cm.MAP_H)
    except Exception:
        pass
    plates = []
    for p in q:
        st = _STATE.get(p["key"], {})
        focus = p["targeted"] or p["hovered"]
        if p["kind"] == "pet" and not PREFS.get("pets", True):
            continue
        if p["rel"] == "self" and not PREFS.get("own", True):
            continue
        bar = _bar_visible(p, st, now)
        name_on = p["show_name"]
        if md == MODE_TARGET and not focus and p["rel"] not in ("self", "npc"):
            name_on = False
            if bar and p["hp"] is not None and p["hp"] >= (p["max"] or 0) and not p["in_combat"]:
                bar = False
            if bar:  # bar-only: 48 x 5
                p["kind_draw"] = "mini"
        p["bar"], p["name_on"] = bar, name_on
        if p.get("kind_draw") == "mini":
            p["_kind"] = p["kind"]
            p["kind"] = "pet"
        rect = _layout(client, p, k, dx, dy)
        if p.get("_kind"):
            p["kind"] = p["_kind"]
        if rect is None:
            continue
        p["rect"] = rect
        plates.append(p)
    # nearer the camera (larger feet Y) first -> drawn on top; target always last/front
    plates.sort(key=lambda p: -p["feet"])
    placed = []
    for p in plates:
        r = p["rect"]
        pushes = 0
        p["pushed"] = False
        if not p["targeted"]:
            while pushes < 3 and any(r.colliderect(o) for o in placed):
                r = r.move(0, -(r.h + 3))
                pushes += 1
            if any(r.colliderect(o) for o in placed):
                # collapse to bar only at the original spot
                if p["bar"]:
                    p["name_on"] = False
                    bh = p["bh"]
                    r = pygame.Rect(p["rect"].centerx - p["bw"] // 2, p["rect"].bottom - bh, p["bw"], bh)
                    p["collapsed"] = True
            p["pushed"] = pushes > 0
        p["anchor"] = (p["rect"].centerx, p["rect"].bottom + 2)
        r.x = max(view.x + 4, min(view.right - 4 - r.w, r.x))
        r.y = max(view.y + 4, min(view.bottom - 4 - r.h, r.y))
        st = _STATE.setdefault(p["key"], {})
        prev = st.get("pos")
        if prev and abs(prev[0] - r.x) < 60 and abs(prev[1] - r.y) < 60:
            nx = prev[0] + (r.x - prev[0]) * 0.25
            ny = prev[1] + (r.y - prev[1]) * 0.25
        else:
            nx, ny = float(r.x), float(r.y)
        st["pos"] = (nx, ny)
        r = pygame.Rect(int(round(nx)), int(round(ny)), r.w, r.h)
        p["rect"] = r
        placed.append(r)
    order = [p for p in plates if not p["targeted"]][::-1] + [p for p in plates if p["targeted"]]
    for p in order:
        _draw(client, p, now)
    # forget units not seen for a while
    for key in [kk for kk, st in _STATE.items() if now - st.get("seen", now) > 30]:
        _STATE.pop(key, None)
    target = next((p for p in plates if p["targeted"]), None)
    if target is not None:
        try:
            target_frame(client, target)
        except Exception as e:  # pragma: no cover
            print("[nameplates] target frame:", e)
    else:
        client.np_target_frame_rect = None
    client._np_last = plates
    return plates


def _draw(client, p, now):
    screen = client.screen
    r = p["rect"]
    alpha = 255 if (p["targeted"] or p["hovered"]) else (209 if (p.get("pushed") or p.get("collapsed")) else 255)
    lay = pygame.Surface((r.w + 8, r.h + 8), pygame.SRCALPHA)
    ox, oy = 4, 4
    if p.get("pushed"):
        ax, ay = p["anchor"]
        pygame.draw.line(screen, (*RIM_TARGET,), (r.centerx, r.bottom), (ax, ay), 1)
    y = oy
    if p["name_on"]:
        nh = p["nh"]
        row = pygame.Rect(ox, y, r.w, nh)
        pygame.draw.rect(lay, ROW_FILL, row, border_radius=4)
        rim = RIM_TARGET if p["targeted"] else (RIM_HOVER if p["hovered"] else RIM)
        pygame.draw.rect(lay, rim, row, 1, border_radius=4)
        xx = row.x + 5
        if p["stars"] is not None:
            _star(lay, xx + 5, row.centery, 6, (70, 120, 200) if p["stars"] > 0 else (150, 150, 150), p["stars"])
            xx += p["sw"]
        f = _font(9 if p["kind"] == "pet" else 11)
        col = p["name_color"] or NAME.get("pet" if p["kind"] == "pet" else p["rel"], NAME["neutral"])
        _stroke_text(lay, p["label"], f, col, midleft=(xx, row.centery))
        if p["level"] is not None:
            lc = level_band(p["level"], _player_cl(client)) if p["kind"] == "mon" or p["rel"] == "hostile" else CHIP_NEUTRAL
            chip = pygame.Rect(row.right - 3 - p["lw"] + 2, row.y + 3, p["lw"] - 2, nh - 6)
            pygame.draw.rect(lay, (0, 0, 0, 200), chip, border_radius=3)
            pygame.draw.rect(lay, lc, chip, 1, border_radius=3)
            _stroke_text(lay, str(p["level"]), _font(9), lc, center=chip.center)
        y += nh + 2
    if p["bar"]:
        bw, bh = p["bw"], p["bh"]
        if p.get("kind_draw") == "mini" or (p.get("collapsed") and False):
            bw, bh = 48, 5
        bx = ox + (r.w - bw) // 2
        by = oy + r.h - bh
        hp, mx = max(0, p["hp"]), max(1, p["max"])
        st = _STATE.get(p["key"], {})
        rel = "friendly" if p["rel"] in ("self", "party") or p["kind"] == "pet" else (
            "hostile" if p["rel"] == "hostile" else "neutral")
        base, hi = FILL[rel]
        pct = hp / mx
        if pct < 0.25:  # 1 Hz brightness pulse 100 -> 130 %
            a = 0.5 + 0.5 * math.sin(now * 2 * math.pi)
            base = tuple(min(255, int(c * (1 + 0.3 * a))) for c in base)
            hi = tuple(min(255, int(c * (1 + 0.3 * a))) for c in hi)
        pygame.draw.rect(lay, OUTLINE, (bx - 1, by - 1, bw + 2, bh + 2))
        pygame.draw.rect(lay, TROUGH, (bx, by, bw, bh))
        trail = _trail(st, hp, mx, now) if st else hp
        if trail > hp:
            tw = int(bw * min(1.0, trail / mx))
            pygame.draw.rect(lay, CHUNK, (bx, by, tw, bh))
        fw = int(round(bw * pct))
        if fw > 0:
            pygame.draw.rect(lay, base, (bx, by, fw, bh))
            pygame.draw.rect(lay, hi, (bx, by, fw, max(1, int(bh * 0.35))))
            if now - st.get("flash", 0) < 0.2:
                pygame.draw.rect(lay, (255, 255, 255, 90), (bx, by, fw, bh))
        if p["targeted"]:
            pygame.draw.rect(lay, RIM_TARGET, (bx - 3, by - 3, bw + 6, bh + 6), 1)
        if _numbers_on(p) and bh >= 8:
            _stroke_text(lay, f"{_short(hp)}/{_short(mx)}", _font(8), (255, 255, 255), center=(bx + bw // 2, by + bh // 2))
    if alpha < 255:
        lay.set_alpha(alpha)
    screen.blit(lay, (r.x - ox, r.y - oy))
    if p["banner"] and p["name_on"]:
        try:
            import mercenaries_ui
            h = p["nh"] + 4
            mercenaries_ui.draw_house_banner(screen, p["banner"], pygame.Rect(r.x - int(h * 0.78) - 3, r.y - 2, int(h * 0.78), h))
        except Exception:
            pass


def _player_cl(client):
    try:
        return client.player_combat_level()
    except Exception:
        return 1


def target_ring(client, cx, feet, sprite_w, rel="hostile"):
    """Ellipse at the feet: 2 px line + 6 px glow at 25 %, 4 gold ticks rotating every 6 s."""
    col = FILL["hostile" if rel == "hostile" else ("friendly" if rel in ("self", "party") else "neutral")][0]
    rx = int(sprite_w * 0.8)
    ry = max(6, int(rx * 0.38))
    rect = pygame.Rect(0, 0, rx * 2, ry * 2)
    rect.center = (int(cx), int(feet))
    lay = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
    inner = pygame.Rect(8, 8, rect.w, rect.h)
    pygame.draw.ellipse(lay, (*col, 64), inner.inflate(4, 4), 6)
    pygame.draw.ellipse(lay, (*col, 255), inner, 2)
    ang = (time.time() % 6.0) / 6.0 * 2 * math.pi
    for kq in range(4):
        a = ang + kq * math.pi / 2 + math.pi / 4
        px = inner.centerx + rx * math.cos(a)
        py = inner.centery + ry * math.sin(a)
        pts = [(px, py), (px + 5 * math.cos(a + 2.6), py + 5 * math.sin(a + 2.6) * 0.6),
               (px + 5 * math.cos(a - 2.6), py + 5 * math.sin(a - 2.6) * 0.6)]
        pygame.draw.polygon(lay, RIM_TARGET, pts)
    client.screen.blit(lay, (rect.x - 8, rect.y - 8))


def target_frame(client, p):
    """HUD target frame (190 x 46) next to the zone badge, top-left of the map."""
    screen = client.screen
    rect = pygame.Rect(132, 8, 190, 46)
    client.np_target_frame_rect = rect
    lay = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(lay, (20, 16, 12, 230), lay.get_rect(), border_radius=5)
    pygame.draw.rect(lay, RIM_TARGET, lay.get_rect(), 2, border_radius=5)
    pygame.draw.rect(lay, (90, 70, 48), lay.get_rect().inflate(-6, -6), 1, border_radius=4)
    screen.blit(lay, rect.topleft)
    try:
        import hud_skin
        tf = hud_skin.font("body", 14)
    except Exception:
        tf = _font(12)
    rel = p["rel"] if p["rel"] in NAME else "neutral"
    lv = p["level"]
    lc = level_band(lv, _player_cl(client)) if lv is not None else CHIP_NEUTRAL
    lt = f"Lv {lv}" if lv is not None else ""
    lsurf = _font(10).render(lt, True, lc)
    name = _fit(tf, p["name"], rect.w - 30 - lsurf.get_width())
    _stroke_text(screen, name, tf, NAME.get(rel, NAME["neutral"]), midleft=(rect.x + 10, rect.y + 13))
    if lt:
        _stroke_text(screen, lt, _font(10), lc, midleft=(rect.right - 10 - lsurf.get_width(), rect.y + 13))
    sub = "HOSTILE" if rel == "hostile" else ("ARENA OPPONENT" if p.get("stars") is not None else
                                              ("PARTY" if rel == "party" else ("YOU" if rel == "self" else "NEUTRAL")))
    if p.get("stars") is not None:
        sub += f"  |  {p['stars']} STAR"
    _stroke_text(screen, sub, _font(7), (180, 165, 130), midleft=(rect.x + 10, rect.y + 25))
    if p["hp"] is not None and p["max"]:
        bx, by, bw, bh = rect.x + 10, rect.y + 30, rect.w - 20, 10
        pygame.draw.rect(screen, OUTLINE, (bx - 1, by - 1, bw + 2, bh + 2))
        pygame.draw.rect(screen, TROUGH, (bx, by, bw, bh))
        relf = "friendly" if rel in ("self", "party") else ("hostile" if rel == "hostile" else "neutral")
        fw = int(bw * max(0, p["hp"]) / max(1, p["max"]))
        pygame.draw.rect(screen, FILL[relf][0], (bx, by, fw, bh))
        pygame.draw.rect(screen, FILL[relf][1], (bx, by, fw, 3))
        pct = int(100 * max(0, p["hp"]) / max(1, p["max"]))
        _stroke_text(screen, f"{_short(p['hp'])}/{_short(p['max'])}  ({pct}%)", _font(8), (255, 255, 255),
                     center=(bx + bw // 2, by + bh // 2))
