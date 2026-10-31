"""Boss duel HUD + input (client side of server/arena_duel.py).

Keys (only while a boss duel is live):
  Q light / quick shot   E heavy / charged shot   F parry (melee)   Space dodge
  A step back   D step in   R FINISH (when the crowd demands it)
The action bar under the map is clickable too.
"""
from __future__ import annotations

import os
import math

import pygame

KEYS = {pygame.K_q: "light", pygame.K_e: "heavy", pygame.K_f: "parry", pygame.K_SPACE: "dodge",
        pygame.K_a: "back", pygame.K_d: "forward", pygame.K_r: "finish"}
CALLOUTS = {"parried": ("PARRY", (255, 220, 120)), "dodged": ("DODGE", (170, 220, 255)),
            "guard_break": ("GUARD BROKEN", (255, 170, 90)), "second_wind": ("SECOND WIND!", (255, 120, 90)),
            "rolled_past": ("ROLLED PAST", (170, 220, 255)), "cornered": ("NO ROOM", (230, 120, 110))}
GOLD = (220, 178, 92)


def duel(client):
    m = getattr(client, "arena_match", None) or {}
    return m.get("duel") if m.get("active") else None


def on_message(client, msg):
    m = getattr(client, "arena_match", None)
    if not m:
        return
    m["duel"] = msg.get("duel") or {}
    now = pygame.time.get_ticks()
    fx = m.setdefault("duel_fx", [])
    for e in msg.get("events") or []:
        k = e.get("kind")
        if k in CALLOUTS:
            text, col = CALLOUTS[k]
            if e.get("perfect"):
                text = "PERFECT " + text
            fx.append({"t": now, "text": text, "col": col})
        elif k == "boss_hit" and "counter" in str(e.get("tag")):
            fx.append({"t": now, "text": "COUNTER!", "col": (255, 236, 160)})
    del fx[:-4]
    _commentary(client, m, msg.get("events") or [])


def _commentary(client, m, events):
    """Keep the log strip and chat in step with the live exchange (not the pre-fight prompt)."""
    try:
        import sys, os as _os
        sd = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "server")
        if sd not in sys.path:
            sys.path.append(sd)
        from arena_duel import exchange_line
    except Exception:
        exchange_line = None
    foe = str(m.get("foe_name") or (m.get("hud") or {}).get("foe_name") or "The champion")
    hud = m.setdefault("hud", {})
    log = list(hud.get("log") or [])
    if not m.get("duel_began"):
        m["duel_began"] = True
        log = [l for l in log if "salutes" not in l and "Start Duel" not in l]
        if not log:
            log.append(f"Duel on vs {foe}!")
        if hasattr(client, "add_chat") and not any(exchange_line and exchange_line(e, foe) for e in events):
            client.add_chat("Arena: " + log[-1], color=(255, 220, 90))
    for e in events:
        line = exchange_line(e, foe) if exchange_line else None
        if not line:
            continue
        log.append(line)
        if hasattr(client, "add_chat") and e.get("kind") not in ("whiff", "boss_miss"):
            client.add_chat("Arena: " + line, color=(255, 220, 90))
    hud["log"] = log[-24:]


def handle_event(client, event) -> bool:
    d = duel(client)
    m = getattr(client, "arena_match", None) or {}
    if not d or (m.get("phase") or "fight") != "fight":
        return False
    if event.type == pygame.KEYDOWN and event.key in KEYS:
        mv = KEYS[event.key]
        if mv == "parry" and d.get("style") == "bow":
            mv = "dodge"
        client.net.send("BARRACKS", action="duel_move", move=mv)
        m["last_move"] = (mv, pygame.time.get_ticks())
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for mv, r in (m.get("duel_btns") or {}).items():
            if r.collidepoint(event.pos):
                client.net.send("BARRACKS", action="duel_move", move=mv)
                m["last_move"] = (mv, pygame.time.get_ticks())
                return True
    return False


def _bar(surf, rect, frac, fill, back=(30, 22, 16), border=GOLD):
    pygame.draw.rect(surf, back, rect, border_radius=4)
    w = int((rect.w - 4) * max(0.0, min(1.0, frac)))
    if w > 0:
        pygame.draw.rect(surf, fill, (rect.x + 2, rect.y + 2, w, rect.h - 4), border_radius=3)
    pygame.draw.rect(surf, border, rect, 1, border_radius=4)


def _label(surf, text, col, bottomleft):
    """Readable bar caption: 19px Cinzel, outlined with a dark shadow, sitting just above the bar."""
    f = font(19)
    s = f.render(text, True, col)
    sh = f.render(text, True, (10, 8, 6))
    x, y = bottomleft[0], bottomleft[1] - 12 - 2 - s.get_height()
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (2, 2)):
        surf.blit(sh, (x + ox, y + oy))
    surf.blit(s, (x, y))
    surf.blit(s, (x + 1, y))   # faux bold: Cinzel is thin at HUD sizes


def draw(client, map_w=900, map_h=640):
    d = duel(client)
    if not d:
        return
    m = client.arena_match
    surf = client.screen
    small = client.font_small
    ui_font = client.font
    t = pygame.time.get_ticks()
    bow = d.get("style") == "bow"
    # --- action bar (bottom centre, above the announcer feed toggle) ---
    labels = [("light", "Q", "Shot" if bow else "Strike"), ("heavy", "E", "Charged" if bow else "Heavy"),
              ("parry", "F", "Parry"), ("dodge", "Spc", "Dodge"), ("back", "A", "Back"),
              ("forward", "D", "Step in")]
    if bow:
        labels = [x for x in labels if x[0] != "parry"]
    bw, bh, gap = 74, 40, 6
    total = len(labels) * bw + (len(labels) - 1) * gap
    x0 = map_w // 2 - total // 2
    y0 = map_h - 92   # under the fighters' feet, above the chat
    btns = {}
    last = m.get("last_move") or ("", 0)
    for i, (mv, key, lab) in enumerate(labels):
        r = pygame.Rect(x0 + i * (bw + gap), y0, bw, bh)
        lit = last[0] == mv and t - last[1] < 220
        pygame.draw.rect(surf, (70, 52, 26) if lit else (24, 18, 12), r, border_radius=6)
        pygame.draw.rect(surf, GOLD if lit else (120, 96, 56), r, 1, border_radius=6)
        surf.blit(small.render(key, True, GOLD), (r.x + 6, r.y + 3))
        s = small.render(lab, True, (240, 226, 196))
        surf.blit(s, s.get_rect(midbottom=(r.centerx, r.bottom - 4)))
        btns[mv] = r
    # stamina + momentum (+ focus)
    sr = pygame.Rect(x0, y0 - 18, total // 2 - 4, 12)
    _bar(surf, sr, float(d.get("sta") or 0) / 100.0, (110, 200, 120))
    _label(surf, "STAMINA", (200, 236, 200), (sr.x, sr.bottom + 0))
    mr = pygame.Rect(sr.right + 8, y0 - 18, total - sr.w - 8, 12)
    mom = float(d.get("momentum") or 0) / 100.0
    _bar(surf, mr, mom, (240, 170, 70) if mom < 1 else (255, 220, 120))
    _label(surf, "CROWD", (250, 214, 150), (mr.x, mr.bottom + 0))
    if bow:
        fr = pygame.Rect(sr.x, y0 - 4, total, 3)
        _bar(surf, fr, float(d.get("focus") or 0), (150, 200, 255), border=(90, 120, 160))
    # FINISH prompt
    if d.get("finisher_ready"):
        pulse = 0.5 + 0.5 * math.sin(t / 120.0)
        s = globals()["font"](18).render("R — FINISHING MOVE" if not bow else "R — FINISHING SHOT", True, (255, 240, 200))
        fr = pygame.Rect(0, 0, s.get_width() + 28, 40)
        fr.midtop = (map_w // 2, 54)  # under the arena plaque, above the fighters' heads
        pygame.draw.rect(surf, (60 + int(60 * pulse), 34, 10), fr, border_radius=8)
        pygame.draw.rect(surf, (255, 220, 120), fr, 2, border_radius=8)
        surf.blit(s, s.get_rect(center=fr.center))
        btns["finish"] = fr
    m["duel_btns"] = btns
    # telegraph over the boss
    tel = d.get("telegraph")
    boss = next((u for u in (m.get("units") or {}).values() if u.get("boss")), None)
    if tel and boss:
        pos = getattr(client, "_duel_boss_screen", None)
        cx, cy = pos if pos else (map_w // 2 + 60, map_h // 2 - 80)
        col = (255, 210, 90) if tel.get("parry") else (240, 70, 60)
        k = max(0.0, min(1.0, float(tel.get("left") or 0) / 6.0))
        rad = int(14 + 26 * k)
        pygame.draw.circle(surf, col, (int(cx), int(cy)), rad, 3)
        pygame.draw.circle(surf, col, (int(cx), int(cy)), 10)
        tip = "PARRY!" if tel.get("parry") and not bow else "DODGE!"
        s = small.render(tip, True, col)
        surf.blit(s, s.get_rect(midbottom=(cx, cy - rad - 2)))
    # callouts
    for i, f in enumerate(list(m.get("duel_fx") or [])):
        age = t - f["t"]
        if age > 900:
            continue
        a = 1 - age / 900.0
        s = ui_font.render(f["text"], True, f["col"])
        s.set_alpha(int(255 * a))
        surf.blit(s, s.get_rect(center=(map_w // 2, map_h // 2 - 40 - int(age / 18) - i * 4)))
    if d.get("rooted"):
        s = ui_font.render("NETTED — can't move", True, (255, 150, 120))
        r = s.get_rect(midbottom=(map_w // 2, y0 - 60))   # above the Stamina/Crowd captions
        surf.blit(ui_font.render("NETTED — can't move", True, (12, 6, 4)), r.move(1, 1))
        surf.blit(s, r)
    if d.get("stunned"):
        s = ui_font.render("STUNNED", True, (255, 150, 120))
        r = s.get_rect(midbottom=(map_w // 2, y0 - 60))   # above the Stamina/Crowd captions
        surf.blit(ui_font.render("STUNNED", True, (12, 6, 4)), r.move(1, 1))
        surf.blit(s, r)


# ---------------------------------------------------------------------------
# Duel stage: painted pit backdrop + the two fighters at duel scale.
# Drawn over the map view while a boss duel is live (the map's small units and
# pips are hidden underneath it).  Falls back silently to the map view if art fails.
# ---------------------------------------------------------------------------
_BG = {}
_FONTS = {}
_STYLE_GEAR = {
    "sword": {"weapon": "steel_sword", "body": "steel_body", "legs": "steel_legs"},
    "axe": {"weapon": "steel_battleaxe", "body": "steel_body", "legs": "steel_legs"},
    "bow": {"weapon": "maple_longbow", "body": "leather_body", "legs": "leather_chaps"},
}
STAGE_FEET = 0.68      # fraction of map height where the fighters stand
HERO_TILE = 158        # player_hd tile size → hero roughly boss height
PX_PER_GAP = 56


def font(size, serif=False):
    k = (size, serif)
    if k not in _FONTS:
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "assets", "fonts", "EBGaramond.ttf" if serif else "Cinzel.ttf")
        try:
            _FONTS[k] = pygame.font.Font(path, size)
        except Exception:
            _FONTS[k] = pygame.font.Font(None, size + 4)
    return _FONTS[k]


def _bg(w, h):
    k = (w, h)
    if k not in _BG:
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            img = pygame.image.load(os.path.join(here, "assets", "castle_realm", "arena", "duel_bg.jpg")).convert()
            iw, ih = img.get_size()
            s = max(w / iw, h / ih)
            img = pygame.transform.smoothscale(img, (int(iw * s) + 1, int(ih * s) + 1))
            out = pygame.Surface((w, h))
            out.blit(img, ((w - img.get_width()) // 2, (h - img.get_height()) // 2))
            # soft vignette so the HUD cards read
            vg = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(24):
                a = int(7 * (24 - i) / 24 * 2)
                pygame.draw.rect(vg, (0, 0, 0, a), (i * 6, i * 4, w - i * 12, h - i * 8), 6)
            out.blit(vg, (0, 0))
            _BG[k] = out
        except Exception:
            _BG[k] = None
    return _BG[k]


def hero_gear(client, style):
    eq = dict(((client.player or {}).get("equipment") or {}))
    gear = dict(_STYLE_GEAR.get(style, _STYLE_GEAR["sword"]))
    # the player's own armour if worn; a style-appropriate weapon always (the duel fixes the style)
    for k in ("body", "legs", "helmet", "shield", "cape"):
        if eq.get(k):
            gear[k] = eq[k]
    w = eq.get("weapon") or ""
    if (style == "bow") == ("bow" in str(w)) and w:
        gear["weapon"] = w
    if style == "bow":
        gear.pop("shield", None)
    return gear


# --- painted HD duel fighters (tools/duel_sprites.py) ---------------------------------------
_SPR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "castle_realm", "arena", "duel_sprites")
_SPR = {}
FIGHTER_H = 0.46      # grounded fighter height as a fraction of map height
RIM_COL = (255, 178, 92)


def _lit(img, rim_dir):
    """Warm grade + soft rim light on the side facing the arena sun."""
    import numpy as np
    rgb = pygame.surfarray.array3d(img).astype(np.float32)
    a = pygame.surfarray.array_alpha(img).astype(np.float32) / 255.0
    rgb *= np.array([1.04, 0.98, 0.90], np.float32)
    dx = 4 * rim_dir
    sh = np.zeros_like(a)
    if dx > 0:
        sh[dx:, :] = a[:-dx, :]
    else:
        sh[:dx, :] = a[-dx:, :]
    sh2 = np.zeros_like(a); sh2[:, 3:] = a[:, :-3]   # light from slightly above
    edge = np.clip(a - np.minimum(sh, sh2), 0, 1)[..., None]
    rgb = rgb * (1 - 0.55 * edge) + np.array(RIM_COL, np.float32) * 0.55 * edge * 1.25
    out = img.copy()
    pygame.surfarray.blit_array(out, np.clip(rgb, 0, 255).astype(np.uint8))
    pa = pygame.surfarray.pixels_alpha(out)
    pa[:] = (a * 255).astype(np.uint8)
    del pa
    return out


def _frame(cid, state, h):
    key = (cid, state, h)
    if key not in _SPR:
        img = pygame.image.load(os.path.join(_SPR_DIR, cid, state + ".png")).convert_alpha()
        sc = h / 380.0
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * sc)), max(1, int(img.get_height() * sc))))
        _SPR[key] = _lit(img, 1 if cid.startswith("hero") else -1)
    return _SPR[key]


def _shadow(surf, x, feet, w, lift):
    k = max(0.45, 1.0 - lift / 160.0)
    w = int(w * k)
    for i, al in enumerate((46, 60, 80, 110)):
        ew, eh = int(w * (1.15 - i * 0.13)), int(w * (0.20 - i * 0.025)) + 4
        e = pygame.Surface((ew, eh), pygame.SRCALPHA)
        pygame.draw.ellipse(e, (12, 6, 2, int(al * k)), (0, 0, ew, eh))
        surf.blit(e, (x - ew // 2, feet - eh // 2 + 2))


def _put(surf, img, x, feet, align):
    """Grounded frames have their feet on the image bottom; airborne ones keep their lift
    because all frames share the sheet's top..baseline crop."""
    r = img.get_rect(midbottom=(x, feet))
    surf.blit(img, r)
    return r


def _states(client, d, m, t, style):
    last = m.get("last_move") or ("", 0)
    age = t - last[1]
    tr = m.setdefault("_duel_track", {"hp": d.get("hp"), "bhp": d.get("boss_hp"), "hit": -9999, "bhit": -9999})
    if (d.get("hp") or 0) < (tr["hp"] or 0) - 1e-4:
        tr["hit"] = t
    if (d.get("boss_hp") or 0) < (tr["bhp"] or 0) - 1e-4:
        tr["bhit"] = t
    tr["hp"], tr["bhp"] = d.get("hp"), d.get("boss_hp")
    hs, hdx = "idle", 0
    if t - tr["hit"] < 380 or d.get("stunned"):
        hs, hdx = "hit", -10
    elif last[0] in ("light", "heavy", "finish") and age < 420:
        hs, hdx = "attack", int(18 * math.sin(math.pi * min(1.0, age / 420.0)))
    elif last[0] in ("dodge", "back") and age < 420:
        hs, hdx = "dodge", -int(26 * math.sin(math.pi * min(1.0, age / 420.0)))
    elif last[0] == "parry" and age < 450:
        hs = "block"
    bst = d.get("boss_state") or "think"
    bs, bdx = "idle", 0
    if bst == "stagger" or t - tr["bhit"] < 380:
        bs, bdx = "hit", 10
    elif bst == "land" or t - tr["hit"] < 380:   # the blow that just landed on the hero
        bs, bdx = "attack", -16
    elif bst == "windup" and d.get("telegraph") and (d["telegraph"].get("left") or 9) <= 1:
        bs, bdx = "attack", -6
    elif d.get("boss_guard"):
        bs = "block"
    elif bst == "recover" and last[0] in ("light", "heavy") and age < 420 and t - tr["bhit"] > 600:
        bs, bdx = "dodge", 14
    return hs, hdx, bs, bdx


def _head_clear(himg, hx, bimg, bx, feet, step=6, most=150):
    """Pixels to slide the hero back so no part of him (weapon included) covers the boss's
    head and helmet crest; bodies and blades may still clash lower down."""
    bb = bimg.get_bounding_rect()
    head = pygame.Rect(bb.x - 4, bb.y, bb.w + 8, max(1, int(bb.h * 0.30)))
    bm = pygame.mask.from_surface(bimg)
    area = pygame.mask.Mask((head.w, head.h)); area.fill()
    headm = pygame.mask.Mask(bimg.get_size())
    headm.draw(area, head.topleft)
    headm = headm.overlap_mask(bm, (0, 0))
    him = pygame.mask.from_surface(himg)
    hr = himg.get_rect(midbottom=(hx, feet)); br = bimg.get_rect(midbottom=(bx, feet))
    for k in range(0, most + 1, step):
        if not headm.overlap(him, (hr.x - k - br.x, hr.y - br.y)):
            return k
    return most


def _draw_painted(client, d, m, surf, t, style, feet, hero_x, boss_x, map_h):
    hid = "hero_" + (style if style in ("sword", "axe", "bow") else "sword")
    bid = d.get("boss_id") or "varro"
    hs, hdx, bs, bdx = _states(client, d, m, t, style)
    h = int(map_h * FIGHTER_H)
    bob = int(2 * math.sin(t / 380.0))
    bimg = _frame(bid, bs, int(h * 1.06))
    himg = _frame(hid, hs, h)
    bl = bimg.get_height() - bimg.get_bounding_rect().bottom   # airborne lift (dodge hops)
    hl = himg.get_height() - himg.get_bounding_rect().bottom
    hdx -= _head_clear(himg, hero_x + hdx, bimg, boss_x + bdx, feet)
    _shadow(surf, boss_x + bdx, feet, int(h * 0.62), max(0, bl))
    _shadow(surf, hero_x + hdx, feet, int(h * 0.55), max(0, hl))
    br = _put(surf, bimg, boss_x + bdx, feet + (bob if bs == "idle" else 0), "w")
    _put(surf, himg, hero_x + hdx, feet - (bob if hs == "idle" else 0), "e")
    client._duel_boss_screen = (boss_x, br.top - 10)


def _draw_rig(client, d, m, surf, t, style, feet, hero_x, boss_x):
    # boss
    import arena_battles_ui as ABU
    bstate = d.get("boss_state") or "think"
    tel = d.get("telegraph")
    banim, bp = "melee", 0.1   # guard stance (the idle west sheet reads as a back view at duel scale)
    if bstate == "land":
        banim, bp = "melee", 0.8
    elif tel:
        banim, bp = "melee", 0.2
    bm = {"boss_id": d.get("boss_id"), "facing": "w", "side": "foe", "stunned": bstate == "stagger"}
    tile_px = 96
    head = None
    try:
        head = ABU.draw_boss(surf, bm, boss_x, feet, tile_px, t / 1000.0, banim, bp, 0, "w")
    except Exception:
        head = None
    if head is None:
        head = feet - 300
    client._duel_boss_screen = (boss_x, head - 30)
    # hero
    last = m.get("last_move") or ("", 0)
    age = t - last[1]
    anim, prog = "idle", None
    if last[0] in ("light", "heavy", "finish") and age < 420:
        anim, prog = ("ranged" if style == "bow" else "melee"), min(1.0, age / 420.0)
    elif style == "bow":
        anim, prog = "ranged", 0.2   # bow held ready (the idle pose slings it on the back)
    sh = pygame.Surface((150, 34), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 100), (0, 0, 150, 34))
    pygame.draw.ellipse(sh, (110, 190, 255, 150), (6, 4, 138, 26), 2)
    surf.blit(sh, (hero_x - 75, feet - 17))
    try:
        import player_hd_client
        look = player_hd_client.get_default_appearance("male", starter=False)
        app = (client.player or {}).get("appearance") or {}
        look.update({k: v for k, v in app.items() if v})
        look["outfit"] = None
        player_hd_client.draw_player(surf, app.get("sex") or "male", look, hero_x, feet, HERO_TILE, t / 1000.0,
                                     anim=anim, progress=prog, facing=1, equipment=hero_gear(client, style),
                                     starter=False)
    except Exception:
        pass


def draw_stage(client, map_w=900, map_h=640):
    """Returns True when the stage was drawn (caller then skips nothing; HUD draws on top)."""
    d = duel(client)
    if not d:
        return False
    m = client.arena_match
    bg = _bg(map_w, map_h)
    if bg is None:
        return False
    surf = client.screen
    surf.blit(bg, (0, 0))
    t = pygame.time.get_ticks()
    style = d.get("style") or "sword"
    gap = float(d.get("gap") or 2.0)
    feet = int(map_h * STAGE_FEET)
    boss_x = int(map_w * 0.60)
    hero_x = max(110, int(boss_x - 135 - gap * PX_PER_GAP))
    try:
        _draw_painted(client, d, m, surf, t, style, feet, hero_x, boss_x, map_h)
        return True
    except Exception:
        pass   # fall back to the old rig art below
    _draw_rig(client, d, m, surf, t, style, feet, hero_x, boss_x)
    return True
    f = font(15)
    for x, text, col in ((hero_x, ((client.player or {}).get("char_name") or "You"), (170, 215, 255)),
                         (boss_x, str((m.get("hud") or {}).get("foe_name") or m.get("foe_name") or ""), (255, 186, 130))):
        s = f.render(text.upper(), True, col)
        bgp = pygame.Surface((s.get_width() + 16, s.get_height() + 4), pygame.SRCALPHA)
        bgp.fill((10, 8, 6, 150))
        r = bgp.get_rect(midtop=(x, feet + 20))
        surf.blit(bgp, r)
        surf.blit(s, s.get_rect(center=r.center))
    return True
