"""Hiscores modal v1 (HISCORES_STYLE_SPEC.md): wood frame, grouped skill list, medal rows,
pinned YOU bar, Jump to my rank and Find player. Visual layer only: data comes from
client.leaderboard exactly as the server sends it (total/guild re-sorted level then XP)."""
import os, time
import pygame
import hud_skin as S

MODAL = pygame.Rect(60, 52, 1080, 708)
GROUPS = [("Overall", ["total", "guild", "endless_depths"]),
          ("Combat", ["attack", "strength", "defence", "archery"]),
          ("Gathering", ["woodcutting", "mining", "fishing"]), ("Crafting", ["cooking", "smithing", "fletching"]),
          ("Social", ["karma", "charisma", "etiquette", "command"])]
LABEL = {"total": "Total", "guild": "Guilds", "endless_depths": "Endless Depths"}
SPRITE = {"attack": "bronze_sword", "strength": "strength_potion", "defence": "bronze_shield",
          "archery": "shortbow", "woodcutting": "bronze_axe", "mining": "bronze_pickaxe",
          "fishing": "raw_shrimp", "cooking": "cooked_lobster", "smithing": "bronze_bar",
          "fletching": "arrow_shaft", "charisma": "ruby_ring", "command": "bone_crown"}
SHAPE = {"guild": "guild", "karma": "moon", "etiquette": "scroll", "endless_depths": "rune"}
MEDAL = [(S._c("#F2C14E"), S._c("#8A6418")), (S._c("#D8DCE4"), S._c("#7A808C")), (S._c("#C8814A"), S._c("#6A3A18"))]
LAUREL = S._c("#6F9A4A"); CREST = S._c("#2B4E8A")
ROW_A, ROW_B = S._c("#3A2E20"), S._c("#2A2118")
ROW_H, PULSE_S = 36, 1.2
_IMG = {}
_ITEMS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "items", "realistic"))


def _sprite(name, size):
    k = (name, size)
    if k not in _IMG:
        try:
            im = pygame.image.load(os.path.join(_ITEMS, name + ".png")).convert_alpha()
            bb = im.get_bounding_rect()
            im = im.subsurface(bb) if bb.w and bb.h else im
            sc = size / max(im.get_width(), im.get_height())
            im = S.brighten_dark(im) or im
            _IMG[k] = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * sc)), max(1, int(im.get_height() * sc))))
        except Exception:
            _IMG[k] = None
    return _IMG[k]


def _label(skill):
    if skill in LABEL:
        return LABEL[skill]
    try:
        import client_screens as cs
        return cs.SKILL_DISPLAY_NAMES.get(skill, skill.title())
    except Exception:
        return skill.title()


def skill_order(client):
    have = list(getattr(client, "leaderboard_skills", None) or list((client.leaderboard or {}).keys()))
    order = [s for _, ss in GROUPS for s in ss]
    if not have:
        return order
    return [s for s in order if s in have] + [s for s in have if s not in order]


def sorted_rows(client, skill):
    rows = list((client.leaderboard or {}).get(skill) or [])
    if skill in ("total", "guild", "endless_depths"):
        # Level then XP (Endless Depths: level = solo deepest floor / room).
        rows.sort(key=lambda e: (-int(e.get("level") or 0), -int(e.get("xp") or 0)))
    return [(i + 1, e) for i, e in enumerate(rows)]


def my_name(client):
    p = getattr(client, "player", None) or {}
    f = getattr(client, "fields", None) or {}
    return str(p.get("char_name") or p.get("name") or f.get("char_name") or f.get("username") or "").strip()


def visible_rows(client, skill):
    rows = sorted_rows(client, skill)
    q = str(getattr(client, "hs_search", "") or "").strip().lower()
    if q:
        rows = [(r, e) for r, e in rows if q in str(e.get("name") or "").lower()]
    return rows


def _st(client):
    if not hasattr(client, "hs_search"):
        client.hs_search = ""
    client.hs_search_focus = getattr(client, "hs_search_focus", False)
    client.hs_pulse = getattr(client, "hs_pulse", 0.0)
    client.hs_rects = getattr(client, "hs_rects", {})


# ---------------------------------------------------------------- pieces
def _medal(surf, cx, cy, rank):
    hi, lo = MEDAL[rank - 1]
    for side in (-1, 1):  # laurel arcs
        for k in range(4):
            a = 2.2 + k * 0.42
            import math
            x = cx + side * int(15 * math.cos(a) * -1); y = cy + int(15 * math.sin(a)) - 4
            pygame.draw.ellipse(surf, LAUREL, (x - 3, y - 2, 6, 4))
    pygame.draw.circle(surf, (0, 0, 0), (cx, cy + 1), 12)
    pygame.draw.circle(surf, lo, (cx, cy), 12)
    pygame.draw.circle(surf, hi, (cx, cy), 10)
    pygame.draw.circle(surf, S._lerp(hi, (255, 255, 255), 0.4), (cx - 3, cy - 3), 3)
    pygame.draw.circle(surf, lo, (cx, cy), 10, 1)
    S.text(surf, str(rank), S.font("title", 13), S.INK, (cx, cy + 1), "center", shadow=False)


def _crest(surf, x, cy):
    pts = [(x, cy - 7), (x + 11, cy - 7), (x + 11, cy + 1), (x + 5, cy + 7), (x, cy + 1)]
    pygame.draw.polygon(surf, CREST, pts)
    pygame.draw.polygon(surf, S.GOLD, pts, 1)
    pygame.draw.line(surf, S.GOLD_HI, (x + 5, cy - 5), (x + 5, cy + 4), 2)
    pygame.draw.line(surf, S.GOLD_HI, (x + 2, cy - 2), (x + 9, cy - 2), 2)


def _star(surf, cx, cy, r, col):
    import math
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    pygame.draw.polygon(surf, col, pts)


def _skill_icon(surf, skill, cx, cy):
    S.medallion(surf, cx, cy, 12, fill=S._c("#4A3A28"))
    if skill == "total":
        _star(surf, cx, cy, 7, S.GOLD_HI); return
    if skill in SPRITE:
        im = _sprite(SPRITE[skill], 21)
        if im is not None:
            surf.blit(im, im.get_rect(center=(cx, cy))); return
    S.icon(surf, SHAPE.get(skill, "rune"), cx, cy, 6)


def _fit(f, s, w):
    if f.size(s)[0] <= w:
        return s
    while s and f.size(s + "...")[0] > w:
        s = s[:-1]
    return s + "..."


def _backdrop(surf):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (w // 10, h // 10))
    surf.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))
    veil = pygame.Surface((w, h), pygame.SRCALPHA); veil.fill((2, 3, 5, 153)); surf.blit(veil, (0, 0))


# ---------------------------------------------------------------- draw
def draw(client):
    _st(client)
    surf = client.screen
    now = time.time()
    mx, my = pygame.mouse.get_pos()
    R = client.hs_rects = {}
    _backdrop(surf)
    S.card(surf, MODAL, r=14, ornate=True)
    # title plaque straddling the top edge, red ribbon tails
    plaque = pygame.Rect(0, 0, 440, 52); plaque.center = (MODAL.centerx, MODAL.y + 2)
    for side in (-1, 1):
        x0 = plaque.left if side < 0 else plaque.right
        tail = [(x0, plaque.y + 10), (x0 + side * 36, plaque.y + 6), (x0 + side * 24, plaque.centery),
                (x0 + side * 36, plaque.bottom - 6), (x0, plaque.bottom - 10)]
        pygame.draw.polygon(surf, S._c("#6E1E18"), tail); pygame.draw.polygon(surf, S.GOLD, tail, 1)
    S.card(surf, plaque, r=8, base=S.WOOD_DK)
    S.text(surf, "HISCORES", S.font("title", 26), S.GOLD_HI, (plaque.centerx, plaque.y + 19), "center")
    S.text(surf, "Top Players & Guilds", S.font("body", 14), S.TITLE, (plaque.centerx, plaque.y + 40), "center")
    # close X (danger, drawn as lines)
    xr = R["close"] = pygame.Rect(MODAL.right - 46, MODAL.y + 12, 32, 32)
    S.button(surf, xr, "danger", hover=xr.collidepoint(mx, my))
    for a, b in (((-6, -6), (6, 6)), ((-6, 6), (6, -6))):
        pygame.draw.line(surf, S.DANGER_TXT, (xr.centerx + a[0], xr.centery + a[1]), (xr.centerx + b[0], xr.centery + b[1]), 3)

    skills = skill_order(client)
    if client.leaderboard_skill not in skills:
        client.leaderboard_skill = "total" if "total" in skills else skills[0]
    cur = client.leaderboard_skill
    # ---- left grouped skill list
    lw = pygame.Rect(MODAL.x + 18, MODAL.y + 46, 214, MODAL.h - 64)
    S.well(surf, lw, 8)
    y = lw.y + 8
    R["skills"] = {}
    hf, bf = S.font("label", 11), S.font("label", 13)
    for gname, gs in GROUPS:
        gs = [s for s in gs if s in skills]
        if not gs:
            continue
        S.text(surf, gname.upper(), hf, S._c("#9C8862"), (lw.x + 10, y), shadow=False)
        tw = hf.size(gname.upper())[0]
        pygame.draw.line(surf, S._c("#5A4630"), (lw.x + 16 + tw, y + 7), (lw.right - 10, y + 7))
        y += 17
        for s in gs:
            r = pygame.Rect(lw.x + 8, y, lw.w - 22, 28)
            R["skills"][s] = r
            act = s == cur
            S.button(surf, r, "active" if act else "idle", inset=act, hover=r.collidepoint(mx, my) and not act, r=5)
            _skill_icon(surf, s, r.x + 16, r.centery)
            S.text(surf, _label(s), bf, S.ACTIVE_TXT if act else S.IDLE_TXT, (r.x + 34, r.centery + 1), "midleft")
            if act:  # gold pointer at right edge
                pygame.draw.polygon(surf, S.GLOW, [(r.right + 1, r.centery - 6), (r.right + 9, r.centery), (r.right + 1, r.centery + 6)])
            y += 31
        y += 4

    guild = cur == "guild"
    rows_all = sorted_rows(client, cur)
    rows = visible_rows(client, cur)
    me = my_name(client).lower()
    my_rank = next(((rk, e) for rk, e in rows_all if me and str(e.get("name") or "").lower() == me), None) if not guild else None
    # ---- header
    rx = lw.right + 18; rw = MODAL.right - 18 - rx
    endless = cur == "endless_depths"
    title = (
        "TOTAL RANKINGS" if cur == "total" else
        "GUILD RANKINGS" if guild else
        "ENDLESS DEPTHS" if endless else
        _label(cur).upper() + " RANKINGS"
    )
    S.text(surf, title, S.font("title", 22), S.GOLD_HI, (rx, MODAL.y + 48))
    n = len(rows_all)
    if cur == "total":
        sub_core = "All skills combined"
    elif guild:
        sub_core = "Combined member levels"
    elif endless:
        sub_core = "Solo deepest floor (each room = 1 level)"
    else:
        sub_core = _label(cur) + " level"
    sub = sub_core + f"  \u00b7  {n} ranked {'guilds' if guild else 'players'}"
    sub = sub.replace("\u00b7", "-")  # Mac font: keep ASCII
    S.text(surf, sub, S.font("body", 14), S.MUTED, (rx, MODAL.y + 76), shadow=False)
    # Jump + Find player
    jr = R["jump"] = pygame.Rect(MODAL.right - 18 - 150, MODAL.y + 52, 150, 32)
    can_jump = my_rank is not None
    S.button(surf, jr, "idle", hover=jr.collidepoint(mx, my) and can_jump, disabled=not can_jump)
    S.text(surf, "JUMP TO MY RANK", S.font("label", 11), S.IDLE_TXT, jr.center, "center")
    sr = R["search"] = pygame.Rect(jr.x - 12 - 210, jr.y + 1, 210, 30)
    S.well(surf, sr, 14, fill=(16, 11, 7))
    if client.hs_search_focus:
        pygame.draw.rect(surf, S.GOLD_HI, sr, 1, border_radius=14)
    pygame.draw.circle(surf, S.GOLD, (sr.x + 16, sr.centery - 2), 6, 2)  # magnifier as shapes
    pygame.draw.line(surf, S.GOLD, (sr.x + 20, sr.centery + 2), (sr.x + 25, sr.centery + 7), 3)
    q = client.hs_search
    tf = S.font("body", 15)
    if q:
        shown = q
        while shown and tf.size(shown)[0] > sr.w - 64:
            shown = shown[1:]
        S.text(surf, shown, tf, S.ACTIVE_TXT, (sr.x + 32, sr.centery), "midleft", shadow=False)
        cx = sr.x + 33 + tf.size(shown)[0]
        cl = R["search_clear"] = pygame.Rect(sr.right - 26, sr.centery - 9, 18, 18)
        for a, b in (((-4, -4), (4, 4)), ((-4, 4), (4, -4))):
            pygame.draw.line(surf, S.MUTED, (cl.centerx + a[0], cl.centery + a[1]), (cl.centerx + b[0], cl.centery + b[1]), 2)
    else:
        S.text(surf, "Find player...", tf, S._c("#7A6A50"), (sr.x + 32, sr.centery), "midleft", shadow=False)
        cx = sr.x + 32
    if client.hs_search_focus and int(now * 2) % 2 == 0:
        pygame.draw.line(surf, S.GOLD_HI, (cx, sr.y + 7), (cx, sr.bottom - 8), 1)

    # ---- table
    tw_ = pygame.Rect(rx, MODAL.y + 98, rw, MODAL.h - 98 - 104)
    S.well(surf, tw_, 6)
    hb = pygame.Rect(tw_.x + 6, tw_.y + 6, tw_.w - 30, 28)
    S.button(surf, hb, "idle", r=4)
    cols = _columns(hb, guild, cur)
    hf2 = S.font("label", 12)
    for key, lab, x, al in cols:
        S.text(surf, lab, hf2, S.GOLD_HI, (x, hb.centery + 1), {"c": "center", "l": "midleft", "r": "midright"}[al])
    body = pygame.Rect(hb.x, hb.bottom + 4, hb.w, tw_.bottom - 6 - hb.bottom - 4)
    view_h = body.h
    max_scroll = max(0, len(rows) * ROW_H - view_h)
    client.leaderboard_max_scroll = max_scroll
    client.leaderboard_scroll = max(0, min(max_scroll, int(getattr(client, "leaderboard_scroll", 0) or 0)))
    R["body"] = body; R["rows"] = []
    clip = surf.get_clip(); surf.set_clip(body)
    if not rows:
        msg = (f"No player named \"{q}\" in the top {n}" if q else
               ("No guilds yet - found one!" if guild else "No players yet - be the first!"))
        S.text(surf, msg, S.font("body", 17), S.MUTED, (body.centerx, body.y + 40), "center")
    first = client.leaderboard_scroll // ROW_H
    nf, nf_b, numf = S.font("body", 16), S.font("label", 15), S.font("label", 15)
    pulse_on = now - client.hs_pulse < PULSE_S
    for i in range(first, min(len(rows), first + view_h // ROW_H + 2)):  # virtualised
        rank, e = rows[i]
        y = body.y + i * ROW_H - client.leaderboard_scroll
        rr = pygame.Rect(body.x, y, body.w, ROW_H - 3)
        base = ROW_A if i % 2 == 0 else ROW_B
        if rank <= 3:
            base = S._lerp(base, MEDAL[rank - 1][0], 0.25)
        hover = rr.collidepoint(mx, my) and body.collidepoint(mx, my)
        if hover:
            base = S._lerp(base, (255, 255, 255), 0.08)
        pygame.draw.rect(surf, base, rr, border_radius=4)
        pygame.draw.line(surf, S._lerp(base, (255, 255, 255), 0.12), (rr.x + 4, rr.y), (rr.right - 5, rr.y))
        mine = (not guild) and me and str(e.get("name") or "").lower() == me
        if mine:
            if pulse_on:
                S.glow(surf, rr, S.PULSE, 6, int(200 * (1 - (now - client.hs_pulse) / PULSE_S)) + 40, 4)
            pygame.draw.rect(surf, S.GLOW, rr, 2, border_radius=4)
        elif hover:
            pygame.draw.rect(surf, S.GOLD_HI, rr, 1, border_radius=4)
        R["rows"].append((rr, e))
        cy = rr.centery
        for key, lab, x, al in cols:
            if key == "rank":
                if rank <= 3:
                    _medal(surf, x, cy, rank)
                else:
                    S.text(surf, f"{rank:,}", numf, S.IDLE_TXT, (x, cy + 1), "center")
            elif key == "name":
                f = nf_b if rank <= 3 else nf
                col = S.GLOW if rank <= 3 else S.ACTIVE_TXT
                nm = _fit(f, str(e.get("name") or "?"), 220)
                S.text(surf, nm, f, col, (x, cy), "midleft")
                if mine:
                    chip = pygame.Rect(x + f.size(nm)[0] + 8, cy - 8, 34, 16)
                    pygame.draw.rect(surf, S.GLOW, chip, border_radius=4)
                    S.text(surf, "YOU", S.font("title", 10), S.INK, chip.center, "center", shadow=False)
            elif key == "guild":
                g = str(e.get("guild") or "")
                if g:
                    _crest(surf, x, cy)
                    S.text(surf, _fit(nf, g, 150), nf, S.TITLE, (x + 17, cy), "midleft")
                else:
                    pygame.draw.line(surf, S.MUTED, (x + 2, cy), (x + 14, cy), 1)
            elif key == "members":
                S.text(surf, f"{int(e.get('members') or 0):,}", numf, S.IDLE_TXT, (x, cy + 1), "midright")
            elif key == "level":
                S.text(surf, f"{int(e.get('level') or 0):,}", numf, S.ACTIVE_TXT, (x, cy + 1), "midright")
            elif key == "xp":
                S.text(surf, f"{int(e.get('xp') or 0):,}", numf, S.ACTIVE_TXT, (x, cy + 1), "midright")
    surf.set_clip(clip)
    # scrollbar: gold-rimmed trough, wood thumb, triangle finials
    tr = pygame.Rect(tw_.right - 20, tw_.y + 18, 12, tw_.h - 36)
    S.well(surf, tr, 5)
    pygame.draw.rect(surf, S.GOLD, tr, 1, border_radius=5)
    S.tri(surf, (tr.centerx, tr.y - 8), True, 5, S.GOLD_HI)
    S.tri(surf, (tr.centerx, tr.bottom + 8), False, 5, S.GOLD_HI)
    if max_scroll:
        th = max(28, int(tr.h * view_h / (len(rows) * ROW_H)))
        ty = tr.y + int((tr.h - th) * client.leaderboard_scroll / max_scroll)
        S.button(surf, pygame.Rect(tr.x, ty, tr.w, th), "active", r=5)
    R["track"] = tr
    # ---- pinned YOU bar
    yb = pygame.Rect(rx, tw_.bottom + 8, rw, 36)
    S.well(surf, yb, 6, fill=(22, 16, 10))
    pygame.draw.rect(surf, S.GOLD, yb, 1, border_radius=6)
    lf = S.font("label", 14)
    if guild:
        S.text(surf, "Guilds rank by combined member levels, then XP", S.font("body", 15), S.MUTED, (yb.x + 16, yb.centery), "midleft", shadow=False)
    elif my_rank:
        rk, e = my_rank
        S.text(surf, f"YOU:  #{rk:,}", S.font("title", 15), S.GLOW, (yb.x + 16, yb.centery), "midleft")
        S.text(surf, str(e.get("name")) + (("  -  " + e["guild"]) if e.get("guild") else ""), S.font("body", 16), S.ACTIVE_TXT, (yb.x + 140, yb.centery), "midleft")
        if endless:
            stats = f"FLOOR {int(e.get('level') or 0):,}"
        elif cur == "total":
            stats = f"TOTAL LVL {int(e.get('level') or 0):,}   {int(e.get('xp') or 0):,} XP"
        else:
            stats = f"LEVEL {int(e.get('level') or 0):,}   {int(e.get('xp') or 0):,} XP"
        S.text(surf, stats, lf, S.GOLD_HI, (yb.right - 16, yb.centery + 1), "midright")
    else:
        S.text(surf, "YOU:  Unranked" + (f" - not in the top {n}" if me and n else " - log in to see your rank"),
               S.font("title", 14), S.MUTED, (yb.x + 16, yb.centery), "midleft")
    # ---- footer keycaps
    fy = MODAL.bottom - 26
    x = rx
    ff = S.font("body", 14)
    for caps, lab in ((["Scroll"], "Browse"), (["up", "down"], "Change skill"), (["Esc"], "Close")):
        for c in caps:
            if c in ("up", "down"):
                r = S.keycap(surf, (x + 8, fy), " ")
                S.tri(surf, r.center, c == "up", 4, S.INK)
                x = r.right + 4
            else:
                w = max(15, S.font("title", 11).size(c.upper())[0] + 6)
                r = S.keycap(surf, (x + w // 2, fy), c.upper()); x = r.right + 4
        S.text(surf, lab, ff, S.MUTED, (x + 3, fy), "midleft", shadow=False)
        x += ff.size(lab)[0] + 26
    S.text(surf, "Guilds = combined member levels / XP", ff, S.MUTED, (MODAL.right - 22, fy), "midright", shadow=False)


def _columns(hb, guild, cur):
    x0, R_ = hb.x, hb.right
    if guild:
        return [("rank", "RANK", x0 + 34, "c"), ("name", "GUILD", x0 + 74, "l"),
                ("members", "MEMBERS", x0 + 470, "r"), ("level", "TOTAL LVL", R_ - 190, "r"), ("xp", "TOTAL XP", R_ - 14, "r")]
    if cur == "endless_depths":
        # Solo deepest room — one floor = one level; hide redundant XP column.
        return [("rank", "RANK", x0 + 34, "c"), ("name", "PLAYER", x0 + 74, "l"),
                ("guild", "GUILD", x0 + 330, "l"), ("level", "FLOOR", R_ - 24, "r")]
    lv = "TOTAL LVL" if cur == "total" else "LEVEL"
    xp = "TOTAL XP" if cur == "total" else "XP"
    return [("rank", "RANK", x0 + 34, "c"), ("name", "PLAYER", x0 + 74, "l"), ("guild", "GUILD", x0 + 330, "l"),
            ("level", lv, R_ - 190, "r"), ("xp", xp, R_ - 14, "r")]


# ---------------------------------------------------------------- input
def jump_to_me(client):
    rows = visible_rows(client, client.leaderboard_skill)
    me = my_name(client).lower()
    for i, (rk, e) in enumerate(rows):
        if me and str(e.get("name") or "").lower() == me:
            body = (getattr(client, "hs_rects", {}) or {}).get("body")
            vh = body.h if body else 400
            client.leaderboard_scroll = max(0, i * ROW_H - vh // 2 + ROW_H // 2)
            client.hs_pulse = time.time()
            return True
    return False


def set_skill(client, s):
    if s != client.leaderboard_skill:
        client.leaderboard_scroll = 0
    client.leaderboard_skill = s


def click(client, pos):
    _st(client)
    R = client.hs_rects or {}
    if R.get("close") and R["close"].collidepoint(pos):
        client.show_leaderboard = False; return True
    for s, r in (R.get("skills") or {}).items():
        if r.collidepoint(pos):
            set_skill(client, s); client.hs_search_focus = False; return True
    if R.get("search_clear") and client.hs_search and R["search_clear"].collidepoint(pos):
        client.hs_search = ""; client.leaderboard_scroll = 0; return True
    if R.get("search") and R["search"].collidepoint(pos):
        client.hs_search_focus = True; return True
    client.hs_search_focus = False
    if R.get("jump") and R["jump"].collidepoint(pos):
        jump_to_me(client); return True
    tr = R.get("track")
    if tr and tr.inflate(8, 24).collidepoint(pos):
        mx = int(getattr(client, "leaderboard_max_scroll", 0) or 0)
        client.leaderboard_scroll = int(mx * max(0.0, min(1.0, (pos[1] - tr.y) / max(1, tr.h))))
        return True
    if not MODAL.collidepoint(pos):
        client.show_leaderboard = False
    return True


def handle_event(client, event):
    """Returns True when consumed. Wheel and the outside-click fall back to legacy if False."""
    _st(client)
    if event.type != pygame.KEYDOWN:
        return False
    if client.hs_search_focus:
        if event.key == pygame.K_ESCAPE:
            if client.hs_search:
                client.hs_search = ""
            else:
                client.hs_search_focus = False
        elif event.key == pygame.K_BACKSPACE:
            client.hs_search = client.hs_search[:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            client.hs_search_focus = False
        elif event.unicode and event.unicode.isprintable() and len(client.hs_search) < 24:
            client.hs_search += event.unicode
        client.leaderboard_scroll = 0
        return True
    if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
        sk = skill_order(client)
        i = sk.index(client.leaderboard_skill) if client.leaderboard_skill in sk else 0
        d = -1 if event.key in (pygame.K_UP, pygame.K_LEFT) else 1
        set_skill(client, sk[(i + d) % len(sk)])
        return True
    if event.key == pygame.K_ESCAPE:
        client.show_leaderboard = False
        return True
    if event.key in (pygame.K_f, pygame.K_SLASH) and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META) or event.key == pygame.K_SLASH):
        client.hs_search_focus = True
        return True
    return False
