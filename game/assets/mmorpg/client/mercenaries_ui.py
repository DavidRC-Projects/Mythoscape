"""Crownfall Arena barracks / practice board UI.

Soldiers are drawn with player_hd armour tiers (bronze→mythos) so each kit
matches the player's own armour art. Opens from Marshal Branna on the arena campus.
"""
from __future__ import annotations

import pygame

import player_hd_client as phd

# Panel chrome
_NAVY = (18, 22, 34)
_NAVY2 = (28, 34, 52)
_GOLD = (220, 180, 70)
_GOLD_DIM = (140, 110, 40)
_TEXT = (235, 230, 210)
_MUTED = (160, 155, 140)
_OK = (90, 190, 110)
_BAD = (210, 90, 80)
_SAND = (210, 170, 70)

_TABS = (
    ("roster", "Roster"),
    ("recruit", "Recruit"),
    ("practice", "Practice"),
)

_HAIR = {
    "levy": "chestnut",
    "man_at_arms": "dark_brown",
    "veteran": "ash_grey",
    "skirmisher": "auburn",
    "bulwark": "black",
    "zealot": "bright_red",
    "duelist": "blonde",
    "medic": "honey",
    "mythos_guard": "white",
}

_PORTRAIT_CACHE = {}
_CHIP_CACHE = {}

# Role colours for cheap list chips (full HD only in the detail modal).
_ROLE_COL = {
    "fodder": (150, 130, 90),
    "line": (90, 120, 160),
    "flank": (140, 110, 70),
    "tank": (100, 110, 130),
    "glass": (170, 70, 70),
    "elite": (180, 150, 60),
    "support": (70, 140, 110),
}


def open_state(client, payload: dict):
    prev_sel = getattr(client, "barracks_selected", None)
    client.barracks = dict(payload or {})
    client.show_barracks = True
    client.dialogue = None
    client.barracks_rects = {}
    roster = client.barracks.get("roster") or []
    ids = {s.get("id") for s in roster}
    # Keep detail modal open on the same soldier after kit/train refresh.
    if prev_sel in ids:
        client.barracks_selected = prev_sel
    else:
        client.barracks_selected = None


def close(client):
    client.show_barracks = False
    client.barracks = None
    client.barracks_rects = {}
    client.barracks_selected = None
    client.barracks_drag = None
    client.barracks_scroll_meta = None


def active(client) -> bool:
    return bool(getattr(client, "show_barracks", False) and getattr(client, "barracks", None))


def result_active(client) -> bool:
    match = getattr(client, "arena_match", None)
    return bool(match and match.get("result") and match.get("awaiting_result", True))


def dismiss_result(client, rematch: bool = False):
    match = getattr(client, "arena_match", None)
    summary = (match or {}).get("result") or {}
    foe_id = summary.get("foe_id")
    client.arena_match = None
    client.arena_result_rects = {}
    client._arena_cam = None
    if rematch and foe_id:
        daily = summary.get("daily") or {}
        if int(daily.get("remaining", 0)) <= 0:
            client.add_chat("No practice fights left today.", color=_BAD)
            client.net.send("BARRACKS", action="open", tab="practice")
            return
        client.net.send("BARRACKS", action="practice", foe_id=foe_id)
        return
    client.net.send("BARRACKS", action="open", tab="practice")


def _match_phase(match) -> str:
    return (
        (match or {}).get("phase")
        or ((match or {}).get("hud") or {}).get("phase")
        or "fight"
    )


def handle_event(client, event) -> bool:
    if result_active(client):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            dismiss_result(client, rematch=False)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return click_result(client, *event.pos)
        return True  # swallow input while result is up
    match = getattr(client, "arena_match", None)
    if match and match.get("active"):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if _match_phase(match) == "preview":
                client.net.send("BARRACKS", action="arena_begin")
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if click_match_hud(client, *event.pos):
                return True
            # Swallow map clicks so the commander doesn't path into the pit.
            mx, my = event.pos
            if mx < 900 and my < 640:
                return True
    if not active(client):
        return False
    if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
        if getattr(client, "barracks_selected", None) is not None:
            client.barracks_selected = None
            return True
        close(client)
        return True
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        client.barracks_drag = None
    if event.type == pygame.MOUSEMOTION and getattr(client, "barracks_drag", None):
        _scrollbar_drag(client, event.pos[1])
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if _scrollbar_mousedown(client, event.pos):
            return True
        return click(client, *event.pos)
    if event.type == pygame.MOUSEWHEEL and active(client):
        meta = getattr(client, "barracks_scroll_meta", None) or {}
        max_scroll = int(meta.get("max_scroll") or 0)
        cur = int(getattr(client, "barracks_scroll", 0) or 0)
        client.barracks_scroll = max(0, min(max_scroll, cur - event.y * 28))
        return True
    return False


def _tab_content_height(tab: str, data: dict) -> int:
    if tab == "roster":
        n = len(data.get("roster") or [])
        if not n:
            return 40
        # bulk strip + field deploy strip + hint + rows
        return 10 + 84 + 44 + 22 + n * 100 + 12
    if tab == "recruit":
        return 12 + len(data.get("recruit") or []) * 108 + 12
    if tab == "practice":
        h = 10 + 28
        if data.get("practice_result"):
            h += 28
        h += len(data.get("practice") or []) * 88 + 12
        return h
    return 0


def _draw_scrollbar(surf, body, scroll: int, content_h: int):
    """Track + thumb along the right edge of the barracks body."""
    view_h = max(1, body.h)
    max_scroll = max(0, content_h - view_h)
    if max_scroll <= 0:
        return {"track": None, "thumb": None, "max_scroll": 0, "view_h": view_h, "content_h": content_h}
    track = pygame.Rect(body.right - 14, body.y + 6, 10, body.h - 12)
    pygame.draw.rect(surf, (16, 20, 30), track, border_radius=5)
    pygame.draw.rect(surf, _GOLD_DIM, track, 1, border_radius=5)
    thumb_h = max(28, int(track.h * view_h / max(1, content_h)))
    thumb_h = min(thumb_h, track.h)
    ratio = scroll / max_scroll if max_scroll else 0
    thumb = pygame.Rect(track.x + 1, track.y + int((track.h - thumb_h) * ratio), track.w - 2, thumb_h)
    pygame.draw.rect(surf, (100, 82, 42), thumb, border_radius=4)
    pygame.draw.rect(surf, _GOLD, thumb, 1, border_radius=4)
    return {
        "track": track,
        "thumb": thumb,
        "max_scroll": max_scroll,
        "view_h": track.h,
        "content_h": content_h,
    }


def _scrollbar_mousedown(client, pos) -> bool:
    meta = getattr(client, "barracks_scroll_meta", None) or {}
    max_scroll = int(meta.get("max_scroll") or 0)
    if max_scroll <= 0:
        return False
    track = meta.get("track")
    thumb = meta.get("thumb")
    if not track:
        return False
    mx, my = pos
    if thumb and thumb.collidepoint(mx, my):
        client.barracks_drag = {"y0": my, "scroll0": int(getattr(client, "barracks_scroll", 0) or 0)}
        return True
    if track.collidepoint(mx, my):
        thumb_h = thumb.h if thumb else 28
        view_h = int(meta.get("view_h") or track.h)
        rel = (my - track.y - thumb_h / 2) / max(1, view_h - thumb_h)
        client.barracks_scroll = max(0, min(max_scroll, int(rel * max_scroll)))
        client.barracks_drag = {"y0": my, "scroll0": client.barracks_scroll}
        return True
    return False


def _scrollbar_drag(client, my: int):
    meta = getattr(client, "barracks_scroll_meta", None) or {}
    drag = getattr(client, "barracks_drag", None)
    max_scroll = int(meta.get("max_scroll") or 0)
    if not drag or max_scroll <= 0:
        return
    thumb = meta.get("thumb")
    thumb_h = thumb.h if thumb else 28
    view_h = int(meta.get("view_h") or 1)
    span = max(1, view_h - thumb_h)
    dy = my - drag["y0"]
    client.barracks_scroll = max(0, min(max_scroll, int(drag["scroll0"] + dy * max_scroll / span)))


def click_match_hud(client, mx, my) -> bool:
    rects = getattr(client, "arena_hud_rects", {}) or {}
    for key, rect in list(rects.items()):
        if hasattr(rect, "collidepoint") and rect.collidepoint(mx, my):
            if key == "feed_toggle":
                client.arena_feed_open = not bool(getattr(client, "arena_feed_open", False))
                return True
            if key == "start_fight":
                client.net.send("BARRACKS", action="arena_begin")
                return True
    return False


def click_result(client, mx, my) -> bool:
    rects = getattr(client, "arena_result_rects", {}) or {}
    for key, rect in list(rects.items()):
        if hasattr(rect, "collidepoint") and rect.collidepoint(mx, my):
            if key == "continue":
                dismiss_result(client, rematch=False)
                return True
            if key == "rematch":
                dismiss_result(client, rematch=True)
                return True
    # Click outside buttons = Continue
    dismiss_result(client, rematch=False)
    return True


def click(client, mx, my) -> bool:
    rects = getattr(client, "barracks_rects", {}) or {}
    detail = rects.get("detail")
    if detail and detail.collidepoint(mx, my):
        # Clicks inside the soldier modal — only modal controls
        for key, rect in list(rects.items()):
            if key in ("panel", "detail") or not hasattr(rect, "collidepoint") or not rect.collidepoint(mx, my):
                continue
            if key == "detail_back":
                client.barracks_selected = None
                return True
            if key.startswith("kit:"):
                sid = getattr(client, "barracks_selected", None)
                if sid is not None:
                    client.net.send("BARRACKS", action="kit", soldier_id=int(sid), tier=key.split(":", 1)[1])
                return True
            if key.startswith("train:"):
                sid = getattr(client, "barracks_selected", None)
                if sid is not None:
                    client.net.send("BARRACKS", action="train", soldier_id=int(sid), skill=key.split(":", 1)[1])
                return True
            if key.startswith("upgrade:"):
                client.net.send(
                    "BARRACKS",
                    action="upgrade",
                    soldier_id=int(key.split(":", 1)[1]),
                    tab="roster",
                )
                return True
            if key.startswith("deploy:"):
                client.net.send(
                    "BARRACKS",
                    action="deploy",
                    soldier_id=int(key.split(":", 1)[1]),
                )
                return True
            if key.startswith("recall:"):
                client.net.send(
                    "BARRACKS",
                    action="recall",
                    soldier_id=int(key.split(":", 1)[1]),
                )
                return True
            if key.startswith("dismiss:"):
                client.net.send("BARRACKS", action="dismiss", soldier_id=int(key.split(":", 1)[1]))
                client.barracks_selected = None
                return True
        return True
    # Click outside detail while open closes the modal only
    if detail and getattr(client, "barracks_selected", None) is not None:
        client.barracks_selected = None
        return True
    panel = rects.get("panel")
    if panel and not panel.collidepoint(mx, my):
        close(client)
        return True
    for key, rect in list(rects.items()):
        if key in ("panel", "detail") or not hasattr(rect, "collidepoint") or not rect.collidepoint(mx, my):
            continue
        if key.startswith("tab:"):
            client.barracks["tab"] = key.split(":", 1)[1]
            client.barracks_scroll = 0
            client.barracks_selected = None
            return True
        if key.startswith("select:"):
            client.barracks_selected = int(key.split(":", 1)[1])
            return True
        if key.startswith("recruit:"):
            client.net.send("BARRACKS", action="recruit", template_id=key.split(":", 1)[1])
            return True
        if key.startswith("upgrade:"):
            client.net.send(
                "BARRACKS",
                action="upgrade",
                soldier_id=int(key.split(":", 1)[1]),
                tab="recruit",
            )
            return True
        if key.startswith("practice:"):
            client.net.send("BARRACKS", action="practice", foe_id=key.split(":", 1)[1])
            return True
        if key.startswith("kit_all:"):
            client.net.send("BARRACKS", action="kit_all", tier=key.split(":", 1)[1])
            return True
        if key.startswith("train_all:"):
            client.net.send("BARRACKS", action="train_all", skill=key.split(":", 1)[1])
            return True
        if key == "deploy_all":
            client.net.send("BARRACKS", action="deploy_all")
            return True
        if key == "recall_all":
            client.net.send("BARRACKS", action="recall_all")
            return True
        if key == "customize_banner":
            client.net.send("BARRACKS", action="customize_banner", tab=data_tab(client))
            return True
        if key == "close":
            close(client)
            return True
    return True


def data_tab(client) -> str:
    return str((getattr(client, "barracks", None) or {}).get("tab") or "roster")


def _soldier_look(template_id: str):
    look = phd.get_default_appearance("male", starter=False)
    look["hair_colour"] = _HAIR.get(template_id, "dark_brown")
    look["outfit"] = None
    return look


def draw_soldier_chip(surf, soldier: dict, cx, cy_feet, tile=40):
    """Lightweight roster/recruit avatar — no HD composite (keeps the board snappy)."""
    tid = soldier.get("template_id") or soldier.get("id") or "levy"
    gear = soldier.get("gear_tier") or soldier.get("default_gear") or "bronze"
    role = soldier.get("role") or ""
    key = (tid, gear, role, int(tile))
    cached = _CHIP_CACHE.get(key)
    if cached is None:
        w = max(28, tile)
        h = max(36, int(tile * 1.35))
        canvas = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        body = _ROLE_COL.get(role, (120, 120, 130))
        # Simple plate silhouette: head + torso + legs + shield notch.
        pygame.draw.ellipse(canvas, (220, 190, 150), (w // 2 - 6, 4, 12, 12))
        pygame.draw.rect(canvas, body, (w // 2 - 10, 14, 20, 18), border_radius=3)
        pygame.draw.rect(canvas, (max(0, body[0] - 25), max(0, body[1] - 25), max(0, body[2] - 20)),
                         (w // 2 - 9, 32, 8, 12), border_radius=2)
        pygame.draw.rect(canvas, (max(0, body[0] - 25), max(0, body[1] - 25), max(0, body[2] - 20)),
                         (w // 2 + 1, 32, 8, 12), border_radius=2)
        pygame.draw.polygon(canvas, _GOLD_DIM, [(w // 2 + 12, 18), (w // 2 + 20, 24), (w // 2 + 12, 30)])
        # Gear tier pip
        pip = {"bronze": (180, 120, 60), "iron": (160, 160, 170), "steel": (140, 150, 165),
               "mithril": (120, 180, 200), "adamant": (90, 160, 110), "mythos": (220, 180, 70)}.get(gear, _GOLD)
        pygame.draw.circle(canvas, pip, (8, 8), 4)
        pygame.draw.circle(canvas, _GOLD_DIM, (8, 8), 4, 1)
        cached = canvas
        if len(_CHIP_CACHE) > 96:
            _CHIP_CACHE.clear()
        _CHIP_CACHE[key] = cached
    surf.blit(cached, (cx - cached.get_width() // 2, cy_feet - cached.get_height() + 4))


def draw_soldier_portrait(surf, soldier: dict, cx, cy_feet, tile=48):
    """Composite player_hd armour art for this soldier's gear tier (detail modal only)."""
    tid = soldier.get("template_id") or "levy"
    gear = soldier.get("gear_tier") or "bronze"
    eq = soldier.get("equipment") or {}
    key = (tid, gear, int(tile), tuple(sorted(eq.items())))
    cached = _PORTRAIT_CACHE.get(key)
    if cached is None:
        pad = tile * 2
        canvas = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        try:
            phd.draw_player(
                canvas, "male", _soldier_look(tid),
                pad, pad + tile // 2, tile, 0.0,
                anim="idle", facing=1, equipment=eq, starter=False,
                fx_ctx={"preview": True, "is_self": False},
            )
        except Exception:
            pygame.draw.ellipse(canvas, _SAND, (pad - tile // 2, pad, tile, tile))
        cached = canvas
        if len(_PORTRAIT_CACHE) > 48:
            # Drop oldest half instead of wiping — avoids hitching on roster refresh.
            for old in list(_PORTRAIT_CACHE.keys())[:24]:
                _PORTRAIT_CACHE.pop(old, None)
        _PORTRAIT_CACHE[key] = cached
    surf.blit(cached, (cx - cached.get_width() // 2, cy_feet - cached.get_height() + tile // 3))


def _btn(surf, font, rects, key, label, rect, bg, fg=_TEXT, border=_GOLD_DIM):
    pygame.draw.rect(surf, bg, rect, border_radius=6)
    pygame.draw.rect(surf, border, rect, 1, border_radius=6)
    text = font.render(label, True, fg)
    surf.blit(text, text.get_rect(center=rect.center))
    rects[key] = rect


def draw_house_banner(surf, banner: dict | None, rect: pygame.Rect):
    """Procedural coat of arms from server banner payload."""
    if not banner:
        pygame.draw.rect(surf, (40, 44, 58), rect, border_radius=4)
        pygame.draw.rect(surf, _GOLD_DIM, rect, 1, border_radius=4)
        return
    # Shield silhouette
    cx, top, w, h = rect.centerx, rect.y, rect.w, rect.h
    tip_y = top + h - 2
    mid_y = top + int(h * 0.62)
    pts = [
        (cx - w // 2 + 2, top + 2),
        (cx + w // 2 - 2, top + 2),
        (cx + w // 2 - 2, mid_y),
        (cx, tip_y),
        (cx - w // 2 + 2, mid_y),
    ]
    primary = tuple(banner.get("primary") or (28, 52, 98))
    secondary = tuple(banner.get("secondary") or (92, 22, 28))
    rim = tuple(banner.get("rim") or _GOLD)
    pygame.draw.polygon(surf, primary, pts)
    part = str(banner.get("partition") or "plain")
    if part == "per_pale":
        clip = [
            (cx, top + 2), (cx + w // 2 - 2, top + 2),
            (cx + w // 2 - 2, mid_y), (cx, tip_y),
        ]
        pygame.draw.polygon(surf, secondary, clip)
    elif part == "per_fess":
        pygame.draw.polygon(surf, secondary, [
            (cx - w // 2 + 2, top + 2), (cx + w // 2 - 2, top + 2),
            (cx + w // 2 - 2, top + h // 2), (cx - w // 2 + 2, top + h // 2),
        ])
    elif part == "quarterly":
        pygame.draw.polygon(surf, secondary, [
            (cx, top + 2), (cx + w // 2 - 2, top + 2),
            (cx + w // 2 - 2, top + h // 2), (cx, top + h // 2),
        ])
        pygame.draw.polygon(surf, secondary, [
            (cx - w // 2 + 2, top + h // 2), (cx, top + h // 2),
            (cx, tip_y), (cx - w // 2 + 2, mid_y),
        ])
    elif part == "bend":
        pygame.draw.polygon(surf, secondary, [
            (cx - w // 2 + 2, top + 8), (cx - w // 2 + 14, top + 2),
            (cx + w // 2 - 2, tip_y - 10), (cx + w // 2 - 14, tip_y),
        ])
    # Simple charge glyph
    charge = str(banner.get("charge") or "star")
    ccol = tuple(banner.get("charge_color") or (230, 210, 120))
    gx, gy = cx, top + int(h * 0.38)
    if charge in ("star", "sun"):
        pygame.draw.circle(surf, ccol, (gx, gy), max(3, w // 7))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            pygame.draw.line(surf, ccol, (gx, gy), (gx + dx * w // 5, gy + dy * w // 5), 2)
    elif charge in ("moon",):
        pygame.draw.circle(surf, ccol, (gx, gy), max(4, w // 6))
        pygame.draw.circle(surf, primary, (gx + 3, gy - 1), max(3, w // 7))
    elif charge in ("crown", "tower", "tree"):
        pygame.draw.rect(surf, ccol, (gx - w // 8, gy - 2, w // 4, h // 5), border_radius=2)
        pygame.draw.polygon(surf, ccol, [
            (gx - w // 6, gy - 2), (gx, gy - h // 6), (gx + w // 6, gy - 2),
        ])
    elif charge in ("sword", "hammer", "anchor"):
        pygame.draw.line(surf, ccol, (gx, gy - h // 7), (gx, gy + h // 6), 3)
        pygame.draw.line(surf, ccol, (gx - w // 8, gy - h // 10), (gx + w // 8, gy - h // 10), 2)
    else:
        # Beast / default — diamond mark
        pygame.draw.polygon(surf, ccol, [
            (gx, gy - h // 8), (gx + w // 7, gy), (gx, gy + h // 8), (gx - w // 7, gy),
        ])
    pygame.draw.polygon(surf, rim, pts, 2)


def _draw_panel_chrome(surf, rect, accent, border=_GOLD, flip_rail=False):
    """Heraldic score card: layered fill, gold rim, accent rail, corner studs."""
    shadow = pygame.Surface((rect.w + 10, rect.h + 10), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 110))
    surf.blit(shadow, (rect.x + 4, rect.y + 5))
    # Outer plate
    plate = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    plate.fill((14, 18, 28, 236))
    surf.blit(plate, rect.topleft)
    # Inner inset
    inset = rect.inflate(-8, -8)
    pygame.draw.rect(surf, (24, 30, 44), inset, border_radius=8)
    # Top banner wash
    banner = pygame.Surface((inset.w, 22), pygame.SRCALPHA)
    banner.fill((*accent, 55))
    surf.blit(banner, inset.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=12)
    # Accent rail
    if flip_rail:
        rail = pygame.Rect(rect.right - 7, rect.y + 12, 5, rect.h - 24)
    else:
        rail = pygame.Rect(rect.x + 2, rect.y + 12, 5, rect.h - 24)
    pygame.draw.rect(surf, accent, rail, border_radius=3)
    # Corner studs
    for cx, cy in (
        (rect.x + 9, rect.y + 9),
        (rect.right - 9, rect.y + 9),
        (rect.x + 9, rect.bottom - 9),
        (rect.right - 9, rect.bottom - 9),
    ):
        pygame.draw.circle(surf, border, (cx, cy), 3)
        pygame.draw.circle(surf, accent, (cx, cy), 1)


def _hp_bar(surf, small, x, y, w, h, cur, mx, fill, glow):
    pygame.draw.rect(surf, (8, 10, 16), (x - 2, y - 2, w + 4, h + 4), border_radius=5)
    pygame.draw.rect(surf, (32, 36, 48), (x, y, w, h), border_radius=4)
    ratio = min(1.0, max(0.0, cur / max(1, mx)))
    fw = int(w * ratio)
    if fw > 0:
        pygame.draw.rect(surf, fill, (x, y, fw, h), border_radius=4)
        pygame.draw.rect(surf, glow, (x, y, fw, max(2, h // 3)), border_radius=3)
        # Segment ticks
        for t in range(1, 4):
            tx = x + int(w * t / 4)
            if tx < x + fw:
                pygame.draw.line(surf, (20, 24, 34), (tx, y + 1), (tx, y + h - 2), 1)
    pct = small.render(f"{int(ratio * 100)}%", True, _TEXT)
    surf.blit(pct, pct.get_rect(midright=(x + w - 5, y + h // 2)))


def _alive_pips(surf, x, y, alive, total, on_col, off_col):
    """Shield-notch tally for living soldiers."""
    n = max(0, min(12, int(total or 0)))
    for i in range(n):
        col = on_col if i < int(alive or 0) else off_col
        px = x + i * 12
        pygame.draw.polygon(surf, col, [(px, y - 3), (px + 4, y), (px, y + 3), (px - 4, y)])


def _count_badge(surf, font, cx, cy, text, accent):
    """Roundel with the alive count."""
    pygame.draw.circle(surf, (10, 12, 18), (cx + 1, cy + 2), 22)
    pygame.draw.circle(surf, accent, (cx, cy), 22)
    pygame.draw.circle(surf, (18, 22, 32), (cx, cy), 18)
    pygame.draw.circle(surf, _GOLD, (cx, cy), 22, 2)
    label = font.render(str(text), True, _TEXT)
    surf.blit(label, label.get_rect(center=(cx, cy)))


def draw_match_hud(client):
    """Top-of-map score cards (stay left of the inventory sidebar)."""
    match = getattr(client, "arena_match", None)
    if not match or not match.get("active"):
        return
    hud = match.get("hud") or {}
    surf = client.screen
    font = client.font
    small = client.font_small
    # Map viewport is 900×640; inventory sidebar starts at x=900 — stay clear of it.
    map_w, map_h = 900, 640
    rects = {}
    phase = _match_phase(match)

    ya = int(hud.get("your_alive") or 0)
    yt = int(hud.get("your_total") or 0)
    fa = int(hud.get("foe_alive") or 0)
    ft = int(hud.get("foe_total") or 0)
    yhp = max(0, int(hud.get("your_hp") or 0))
    ymax = max(1, int(hud.get("your_max_hp") or 1))
    fhp = max(0, int(hud.get("foe_hp") or 0))
    fmax = max(1, int(hud.get("foe_max_hp") or 1))
    foe = hud.get("foe_name") or match.get("foe_name") or "Foe"

    you_col = (86, 168, 230)
    you_glow = (170, 215, 255)
    foe_col = (220, 118, 72)
    foe_glow = (255, 186, 130)

    left = pygame.Rect(10, 10, 268, 100)
    right = pygame.Rect(map_w - 278, 10, 268, 100)
    _draw_panel_chrome(surf, left, you_col, (170, 200, 235), flip_rail=False)
    _draw_panel_chrome(surf, right, foe_col, (235, 180, 120), flip_rail=True)

    # Left — your army
    surf.blit(small.render("YOUR ARMY", True, you_glow), (left.x + 18, left.y + 12))
    _count_badge(surf, font, left.x + 48, left.y + 58, f"{ya}", you_col)
    surf.blit(font.render(f"of {yt}", True, _MUTED), (left.x + 78, left.y + 48))
    _alive_pips(surf, left.x + 82, left.y + 72, ya, yt, you_col, (55, 62, 78))
    _hp_bar(surf, small, left.x + 78, left.y + 80, left.w - 96, 12, yhp, ymax, you_col, you_glow)

    # Right — enemy
    surf.blit(small.render("ENEMY", True, foe_glow), (right.x + 18, right.y + 12))
    ename = small.render(str(foe)[:18], True, _GOLD)
    surf.blit(ename, (right.right - ename.get_width() - 16, right.y + 12))
    _count_badge(surf, font, right.right - 48, right.y + 58, f"{fa}", foe_col)
    surf.blit(font.render(f"of {ft}", True, _MUTED), (right.x + 18, right.y + 48))
    _alive_pips(surf, right.x + 18, right.y + 72, fa, ft, foe_col, (55, 62, 78))
    _hp_bar(surf, small, right.x + 18, right.y + 80, right.w - 96, 12, fhp, fmax, foe_col, foe_glow)

    # Slim centre plaque + commentary dropdown (opens downward)
    feed_open = bool(getattr(client, "arena_feed_open", False))
    log = list(hud.get("log") or [])
    plaque = pygame.Rect(0, 0, 220, 34)
    plaque.midtop = (map_w // 2, 12)
    pbg = pygame.Surface((plaque.w, plaque.h), pygame.SRCALPHA)
    pbg.fill((12, 16, 26, 230))
    surf.blit(pbg, plaque.topleft)
    pygame.draw.rect(surf, _GOLD_DIM, plaque, 1, border_radius=10)
    pygame.draw.line(surf, _GOLD, (plaque.x + 16, plaque.y + 2), (plaque.right - 16, plaque.y + 2), 1)
    title = small.render("CROWNFALL ARENA", True, _GOLD)
    surf.blit(title, title.get_rect(center=(plaque.centerx, plaque.y + 11)))
    status = "Line up" if phase == "preview" else "Live"
    surf.blit(
        small.render(status, True, _SAND if phase == "preview" else _OK),
        small.render(status, True, _SAND if phase == "preview" else _OK).get_rect(
            center=(plaque.centerx, plaque.y + 24)
        ),
    )

    toggle = pygame.Rect(0, 0, 200, 24)
    toggle.midtop = (map_w // 2, plaque.bottom + 6)
    tbg = pygame.Surface((toggle.w, toggle.h), pygame.SRCALPHA)
    tbg.fill((16, 20, 30, 220))
    surf.blit(tbg, toggle.topleft)
    pygame.draw.rect(surf, _GOLD_DIM, toggle, 1, border_radius=8)
    chev = "▴" if feed_open else "▾"
    latest = log[-1] if log else "Commentary"
    label = f"{chev}  Commentary" if feed_open or not log else f"{chev}  {str(latest)[:24]}"
    surf.blit(small.render(label, True, _SAND if feed_open else _MUTED), (toggle.x + 10, toggle.y + 4))
    rects["feed_toggle"] = toggle

    if feed_open:
        feed = pygame.Rect(0, 0, 300, 78)
        feed.midtop = (toggle.centerx, toggle.bottom + 4)
        fbg = pygame.Surface((feed.w, feed.h), pygame.SRCALPHA)
        fbg.fill((10, 14, 22, 240))
        surf.blit(fbg, feed.topleft)
        pygame.draw.rect(surf, _GOLD_DIM, feed, 1, border_radius=8)
        lines = log[-4:] if log else ["Waiting for the first clash…"]
        ly = feed.y + 8
        for line in lines:
            col = _BAD if "falls" in str(line).lower() else _TEXT
            surf.blit(small.render(str(line)[:42], True, col), (feed.x + 12, ly))
            ly += 16

    if phase == "preview":
        btn = pygame.Rect(0, 0, 210, 50)
        btn.center = (map_w // 2, map_h // 2 + 36)
        shadow = pygame.Surface((btn.w + 8, btn.h + 8), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 120))
        surf.blit(shadow, (btn.x + 3, btn.y + 4))
        pygame.draw.rect(surf, (62, 44, 18), btn, border_radius=14)
        pygame.draw.rect(surf, _GOLD, btn, 3, border_radius=14)
        pygame.draw.rect(surf, (90, 68, 28), btn.inflate(-8, -8), 1, border_radius=10)
        label = font.render("Start Battle", True, _SAND)
        surf.blit(label, label.get_rect(center=btn.center))
        rects["start_fight"] = btn
        tip = small.render("Front 5 clash · reserves join on first fall  ·  Space starts", True, _MUTED)
        surf.blit(tip, tip.get_rect(midtop=(btn.centerx, btn.bottom + 10)))

    client.arena_hud_rects = rects


def draw_match_result(client, match: dict):
    """Result card with Continue / Rematch — player dismisses, barracks does not auto-open."""
    summary = match.get("result") or {}
    surf = client.screen
    font = client.font
    big = getattr(client, "font_large", None) or font
    small = client.font_small
    sw, sh = surf.get_size()
    won = bool(summary.get("won"))
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 120))
    surf.blit(veil, (0, 0))

    card = pygame.Rect(0, 0, 540, 300)
    card.center = (sw // 2, sh // 2)
    pygame.draw.rect(surf, _NAVY, card, border_radius=14)
    pygame.draw.rect(surf, _OK if won else _BAD, card, 3, border_radius=14)
    verb = "VICTORY" if won else "DEFEAT"
    title = big.render(verb, True, _OK if won else _BAD)
    surf.blit(title, title.get_rect(midtop=(card.centerx, card.y + 16)))
    winner = summary.get("winner") or ("You" if won else summary.get("foe_name") or "Foe")
    loser = summary.get("loser") or (summary.get("foe_name") if won else "You")
    line = font.render(f"{winner} defeated {loser}", True, _TEXT)
    surf.blit(line, line.get_rect(midtop=(card.centerx, card.y + 64)))

    xp = int(summary.get("command_xp") or 0)
    surf.blit(font.render(f"+{xp} Command XP", True, _GOLD),
              font.render(f"+{xp} Command XP", True, _GOLD).get_rect(midtop=(card.centerx, card.y + 98)))

    ya = int(summary.get("your_alive") or 0)
    fa = int(summary.get("foe_alive") or 0)
    rounds = int(summary.get("rounds") or 0)
    stats = small.render(
        f"Survivors  you {ya}  ·  foe {fa}  ·  {rounds} ticks",
        True, _MUTED,
    )
    surf.blit(stats, stats.get_rect(midtop=(card.centerx, card.y + 132)))

    extras = []
    if summary.get("coins"):
        extras.append(f"+{int(summary['coins']):,} coins")
    if summary.get("mythos_ore"):
        extras.append("Mythos ore!")
    daily = summary.get("daily") or {}
    remaining = int(daily.get("remaining", 0))
    cap = int(daily.get("cap", 10))
    extras.append(f"{remaining}/{cap} fights left today")
    sub = small.render("  ·  ".join(extras), True, _MUTED)
    surf.blit(sub, sub.get_rect(midtop=(card.centerx, card.y + 158)))

    survivors = list(summary.get("survivor_xp") or [])
    if survivors:
        lv_bits = []
        for g in survivors[:4]:
            if g.get("leveled"):
                lv_bits.append(f"{g.get('name')}: {', '.join(g['leveled'][:2])}")
            else:
                lv_bits.append(f"{g.get('name')} +{int(g.get('xp') or 0)} XP")
        more = f"  (+{len(survivors) - 4} more)" if len(survivors) > 4 else ""
        surv = small.render(
            ("Survivors hardened — " + " · ".join(lv_bits) + more)[:90],
            True, _OK,
        )
        surf.blit(surv, surv.get_rect(midtop=(card.centerx, card.y + 182)))

    rects = {}
    can_rematch = remaining > 0 and bool(summary.get("foe_id"))
    cont = pygame.Rect(card.centerx - 200, card.bottom - 58, 170, 40)
    rem = pygame.Rect(card.centerx + 30, card.bottom - 58, 170, 40)
    _btn(surf, font, rects, "continue", "Continue", cont, (40, 70, 45), _OK, _OK)
    if can_rematch:
        _btn(surf, font, rects, "rematch", "Rematch", rem, (70, 50, 20), _SAND, _GOLD)
    else:
        _btn(surf, small, rects, "rematch_locked", "No fights left", rem, (40, 40, 48), _MUTED, _GOLD_DIM)
    tip = small.render("Esc / Enter · Continue", True, _MUTED)
    surf.blit(tip, tip.get_rect(midbottom=(card.centerx, card.bottom - 8)))
    client.arena_result_rects = rects


def draw(client):
    if not active(client):
        return
    data = client.barracks
    surf = client.screen
    font = client.font
    small = client.font_small
    big = getattr(client, "font_large", None) or font
    sw, sh = surf.get_size()
    panel = pygame.Rect(40, 28, min(1120, sw - 80), min(700, sh - 56))
    pygame.draw.rect(surf, _NAVY, panel, border_radius=14)
    pygame.draw.rect(surf, _GOLD, panel, 2, border_radius=14)
    pygame.draw.rect(surf, _GOLD_DIM, panel.inflate(-8, -8), 1, border_radius=12)

    rects = {"panel": panel}
    title = big.render("Crownfall Arena · Barracks", True, _GOLD)
    surf.blit(title, (panel.x + 22, panel.y + 14))
    cmd = int(data.get("command_level") or 1)
    total = int(data.get("roster_total_cl") or 0)
    daily = data.get("daily_fights") or {}
    fights = f"{daily.get('used', 0)}/{daily.get('cap', 10)}" if daily else "—"
    purse = int(data.get("coins") or 0)
    bank = int(data.get("bank_coins") or 0)
    n_roster = len(data.get("roster") or [])
    meta = small.render(
        f"Command {cmd}  ·  Army CL {total}  ·  "
        f"{n_roster}/{data.get('roster_max') or 10}  ·  "
        f"Purse {purse:,}  ·  Bank {bank:,}  ·  Fights {fights}",
        True, _MUTED,
    )
    surf.blit(meta, (panel.x + 22, panel.y + 44))
    sub_bits = []
    nxt = data.get("next_unlock")
    if nxt:
        sub_bits.append(f"Next unlock · Cmd {nxt['level']}: {nxt['text']}")
    if data.get("mythos_soldier_ready"):
        sub_bits.append("Mythos Guard unlocked")
    elif cmd < 80:
        sub_bits.append(f"Mythos Guard at Command 80 ({80 - cmd} left)")
    if sub_bits:
        surf.blit(small.render("  ·  ".join(sub_bits)[:110], True, (180, 200, 255)),
                  (panel.x + 22, panel.y + 62))

    _btn(surf, small, rects, "close", "Close",
         pygame.Rect(panel.right - 88, panel.y + 12, 70, 26), (50, 30, 30), _TEXT, _BAD)

    # Personal house crest (David: House of the Creator) + customise.
    house = data.get("personal_house") or {}
    if house.get("name"):
        banner_rect = pygame.Rect(panel.right - 210, panel.y + 10, 44, 52)
        draw_house_banner(surf, house.get("banner"), banner_rect)
        rects["house_banner"] = banner_rect
        hname = small.render(str(house["name"])[:28], True, _GOLD)
        surf.blit(hname, (banner_rect.right + 8, panel.y + 14))
        _btn(
            surf, small, rects, "customize_banner", "Customise banner",
            pygame.Rect(banner_rect.right + 8, panel.y + 36, 118, 24),
            (40, 36, 28), _TEXT, _GOLD_DIM,
        )

    # Practice gets stronger chrome when a fight is ready.
    practice_ready = n_roster > 0 and any(
        f.get("unlocked") and int((daily or {}).get("remaining", 0)) > 0
        for f in (data.get("practice") or [])
    )
    tx = panel.x + 22
    tab = data.get("tab") or "roster"
    for tid, label in _TABS:
        w = 128 if tid == "practice" and practice_ready else 108
        r = pygame.Rect(tx, panel.y + 88, w, 32)
        selected = tid == tab
        if selected:
            bg, border, fg = (55, 48, 28), _GOLD, _GOLD
        elif tid == "practice" and practice_ready:
            bg, border, fg = (50, 42, 22), _SAND, _SAND
        else:
            bg, border, fg = _NAVY2, _GOLD_DIM, _TEXT
        _btn(surf, small, rects, f"tab:{tid}", label, r, bg, fg, border)
        tx += w + 8

    flash = data.get("flash")
    if flash:
        good = any(k in str(flash) for k in ("Victory", "Recruited", "Fitted", "Trained", "→", "banner", "Deployed", "Recalled"))
        ftxt = small.render(str(flash)[:120], True, _OK if good else _TEXT)
        surf.blit(ftxt, (panel.x + 22, panel.y + 126))

    body = pygame.Rect(panel.x + 18, panel.y + 150, panel.w - 36, panel.h - 172)
    pygame.draw.rect(surf, _NAVY2, body, border_radius=8)
    content_h = _tab_content_height(tab if tab not in ("kits", "train") else "roster", data)
    max_scroll = max(0, content_h - body.h)
    scroll = max(0, min(max_scroll, int(getattr(client, "barracks_scroll", 0) or 0)))
    client.barracks_scroll = scroll

    prev_clip = surf.get_clip()
    surf.set_clip(body)
    if tab == "roster" or tab in ("kits", "train"):
        if tab in ("kits", "train"):
            data["tab"] = "roster"
        _draw_roster(client, surf, font, small, body, data, rects, scroll)
    elif tab == "recruit":
        _draw_recruit(client, surf, font, small, body, data, rects, scroll)
    elif tab == "practice":
        _draw_practice(client, surf, font, small, body, data, rects, scroll)
    surf.set_clip(prev_clip)

    client.barracks_scroll_meta = _draw_scrollbar(surf, body, scroll, content_h)
    rects["scroll_track"] = (client.barracks_scroll_meta or {}).get("track")
    rects["scroll_thumb"] = (client.barracks_scroll_meta or {}).get("thumb")

    if getattr(client, "barracks_selected", None) is not None:
        _draw_soldier_detail(client, surf, font, small, big, panel, data, rects)

    client.barracks_rects = rects


def _draw_roster(client, surf, font, small, body, data, rects, scroll):
    soldiers = data.get("roster") or []
    if not soldiers:
        empty = font.render("No soldiers yet — open Recruit, or talk to Marshal Branna on the sand.", True, _MUTED)
        surf.blit(empty, (body.x + 20, body.y + 24))
        return

    y = body.y + 10 - scroll
    list_w = body.w - 28  # leave gutter for scrollbar
    # Bulk strip — two clear rows
    strip = pygame.Rect(body.x + 10, y, list_w, 72)
    pygame.draw.rect(surf, (24, 28, 40), strip, border_radius=8)
    pygame.draw.rect(surf, _GOLD_DIM, strip, 1, border_radius=8)
    surf.blit(small.render("Outfit all", True, _GOLD), (strip.x + 12, strip.y + 8))
    x = strip.x + 92
    for kit in data.get("kits") or []:
        locked = bool(kit.get("locked"))
        label = kit["label"].replace(" kit", "")
        r = pygame.Rect(x, strip.y + 6, 72, 24)
        if r.right > strip.right - 12:
            break
        bg = (50, 30, 30) if locked else _NAVY
        key = f"kit_all:{kit['tier']}" if not locked else f"kit_all_locked:{kit['tier']}"
        _btn(surf, small, rects, key, label, r, bg, _MUTED if locked else _TEXT,
             _BAD if locked else _GOLD_DIM)
        x = r.right + 6
    cap = int(data.get("daily_train_cap") or 10)
    surf.blit(small.render(f"Train all (+1 · {cap}/day each)", True, _GOLD),
              (strip.x + 12, strip.y + 40))
    x = strip.x + 200
    for skill, short in (("attack", "Att"), ("strength", "Str"), ("defence", "Def"), ("hitpoints", "HP")):
        r = pygame.Rect(x, strip.y + 38, 72, 26)
        _btn(surf, small, rects, f"train_all:{skill}", short, r, (40, 55, 70), _TEXT, _GOLD_DIM)
        x = r.right + 6
    y += 84
    # Field deploy — Castle Realm only.
    in_realm = bool(data.get("in_castle_realm"))
    deployed_n = int(data.get("deployed_count") or 0)
    deploy_row = pygame.Rect(body.x + 10, y, list_w, 36)
    pygame.draw.rect(surf, (24, 28, 40), deploy_row, border_radius=8)
    pygame.draw.rect(surf, _GOLD_DIM, deploy_row, 1, border_radius=8)
    hint = (
        f"Field squad  ·  {deployed_n} deployed  ·  follow you in Castle Realm"
        if in_realm else
        "Field squad  ·  enter Castle Realm to deploy"
    )
    surf.blit(small.render(hint, True, _MUTED if not in_realm else _TEXT),
              (deploy_row.x + 12, deploy_row.y + 10))
    if in_realm:
        _btn(surf, small, rects, "deploy_all", "Deploy all",
             pygame.Rect(deploy_row.right - 210, deploy_row.y + 5, 96, 26),
             (40, 70, 45), _OK, _OK)
        _btn(surf, small, rects, "recall_all", "Recall",
             pygame.Rect(deploy_row.right - 106, deploy_row.y + 5, 90, 26),
             (60, 40, 28), _SAND, _GOLD)
    y += 44
    surf.blit(small.render("Click a soldier to kit, train, promote, deploy, or dismiss.", True, _MUTED),
              (body.x + 14, y))
    y += 22

    for s in soldiers:
        row = pygame.Rect(body.x + 10, y, list_w, 92)
        if row.bottom < body.y or row.top > body.bottom:
            y += 100
            continue
        pygame.draw.rect(surf, (32, 36, 50), row, border_radius=8)
        pygame.draw.rect(surf, _GOLD_DIM, row, 1, border_radius=8)
        draw_soldier_chip(surf, s, row.x + 48, row.y + 78, tile=40)
        role = s.get("template_name") or s.get("role") or ""
        daily = s.get("trains_today") or {}
        left = daily.get("remaining", cap)
        name = font.render(
            f"{s.get('name')}  ·  {role}  ·  CL {s.get('combat_level')}  ·  trains {left}/{cap}",
            True, _TEXT,
        )
        surf.blit(name, (row.x + 100, row.y + 12))
        lv = s.get("levels") or {}
        stats = small.render(
            f"Att {lv.get('attack')}  Str {lv.get('strength')}  Def {lv.get('defence')}  HP {lv.get('hitpoints')}  ·  "
            f"{(s.get('gear_tier') or '').title()}  ·  {s.get('ability_label') or '—'}",
            True, _MUTED,
        )
        surf.blit(stats, (row.x + 100, row.y + 38))
        up = s.get("upgrade")
        if s.get("deployed"):
            blurb = small.render("Deployed — following you in the Castle Realm", True, _OK)
        elif up and not up.get("locked"):
            blurb = small.render(
                f"Promote → {up.get('to_name')}  {int(up.get('cost') or 0):,}c  (keeps battle XP)",
                True, _OK,
            )
        elif up and up.get("locked"):
            blurb = small.render(
                f"Next: {up.get('to_name')}  ·  need Command {up.get('command_req')}",
                True, _MUTED,
            )
        else:
            blurb = small.render(str(s.get("blurb") or "")[:70], True, _MUTED)
        surf.blit(blurb, (row.x + 100, row.y + 58))
        rects[f"select:{s['id']}"] = row
        y += 100


def _draw_recruit(client, surf, font, small, body, data, rects, scroll):
    y = body.y + 12 - scroll
    list_w = body.w - 28
    for t in data.get("recruit") or []:
        row = pygame.Rect(body.x + 10, y, list_w, 100)
        if row.bottom < body.y or row.top > body.bottom:
            y += 108
            continue
        locked = bool(t.get("locked"))
        pygame.draw.rect(surf, (40, 28, 28) if locked else (32, 36, 50), row, border_radius=8)
        pygame.draw.rect(surf, _BAD if locked else _GOLD_DIM, row, 1, border_radius=8)
        preview = {
            "template_id": t["id"],
            "id": t["id"],
            "role": {
                "levy": "fodder", "man_at_arms": "line", "veteran": "line",
                "skirmisher": "flank", "bulwark": "tank", "zealot": "glass",
                "duelist": "elite", "medic": "support", "mythos_guard": "elite",
            }.get(t["id"], "line"),
            "gear_tier": t.get("default_gear") or "bronze",
            "default_gear": t.get("default_gear") or "bronze",
        }
        draw_soldier_chip(surf, preview, row.x + 48, row.y + 82, tile=40)
        title = f"{t['name']}  ·  CL {t.get('combat_level')}  ·  {int(t.get('cost') or 0):,}c"
        if locked:
            title += f"  ·  need Command {t.get('command_req')}"
        surf.blit(font.render(title, True, _MUTED if locked else _TEXT), (row.x + 100, row.y + 12))
        surf.blit(small.render(f"{t.get('ability_label')}  ·  train ×{t.get('train_speed')}", True, _MUTED),
                  (row.x + 100, row.y + 38))
        up_from = t.get("upgrade_from")
        if up_from and not locked:
            surf.blit(small.render(
                f"Or promote {up_from.get('soldier_name')} ({up_from.get('from_name')}) "
                f"for {int(up_from.get('cost') or 0):,}c — keeps battle XP",
                True, _OK,
            ), (row.x + 100, row.y + 58))
        else:
            surf.blit(small.render(str(t.get("blurb") or "")[:80], True, _MUTED), (row.x + 100, row.y + 58))
        if not locked:
            _btn(surf, small, rects, f"recruit:{t['id']}", "Recruit",
                 pygame.Rect(row.right - 100, row.y + 18, 88, 28), (40, 70, 45), _OK, _OK)
            if up_from:
                _btn(
                    surf, small, rects, f"upgrade:{up_from['soldier_id']}",
                    f"Upgrade {int(up_from.get('cost') or 0):,}c",
                    pygame.Rect(row.right - 100, row.y + 52, 88, 28),
                    (55, 48, 28), _SAND, _GOLD,
                )
        y += 108


def _selected_soldier(data, client):
    sid = getattr(client, "barracks_selected", None)
    for s in data.get("roster") or []:
        if s.get("id") == sid:
            return s
    return None


def _draw_soldier_detail(client, surf, font, small, big, panel, data, rects):
    """Two-column modal: portrait/stats left, gear right, train below, dismiss bottom-right."""
    soldier = _selected_soldier(data, client)
    if not soldier:
        client.barracks_selected = None
        return
    veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 140))
    surf.blit(veil, (0, 0))

    card = pygame.Rect(0, 0, min(760, panel.w - 40), min(540, panel.h - 40))
    card.center = panel.center
    pygame.draw.rect(surf, _NAVY, card, border_radius=14)
    pygame.draw.rect(surf, _GOLD, card, 2, border_radius=14)
    rects["detail"] = card

    role = soldier.get("template_name") or soldier.get("role") or ""
    title = big.render(f"{soldier.get('name')}  ·  {role}", True, _GOLD)
    surf.blit(title, (card.x + 20, card.y + 14))
    _btn(surf, small, rects, "detail_back", "Back",
         pygame.Rect(card.right - 88, card.y + 12, 70, 26), (50, 40, 28), _TEXT, _GOLD_DIM)

    # Left column
    draw_soldier_portrait(surf, soldier, card.x + 90, card.y + 175, tile=64)
    lv = soldier.get("levels") or {}
    daily = soldier.get("trains_today") or {}
    cap = int(daily.get("cap") or data.get("daily_train_cap") or 10)
    trains_left = int(daily.get("remaining", cap))
    lx = card.x + 24
    ly = card.y + 200
    surf.blit(font.render(
        f"CL {soldier.get('combat_level')}  ·  {(soldier.get('gear_tier') or '').title()}",
        True, _TEXT,
    ), (lx, ly))
    ly += 26
    surf.blit(small.render(
        f"Att {lv.get('attack')}  Str {lv.get('strength')}  "
        f"Def {lv.get('defence')}  HP {lv.get('hitpoints')}",
        True, _MUTED,
    ), (lx, ly))
    ly += 20
    surf.blit(small.render(
        f"{soldier.get('ability_label') or '—'}  ·  train ×{soldier.get('train_speed')}  ·  "
        f"{trains_left}/{cap} trains today",
        True, _MUTED if trains_left > 0 else _BAD,
    ), (lx, ly))
    ly += 20
    purse = int(data.get("coins") or 0)
    bank = int(data.get("bank_coins") or 0)
    surf.blit(small.render(f"Purse {purse:,}  ·  Bank {bank:,}", True, _MUTED), (lx, ly))
    if soldier.get("blurb"):
        ly += 20
        surf.blit(small.render(str(soldier["blurb"])[:42], True, _MUTED), (lx, ly))

    # Right column — gear list
    rx = card.x + 320
    surf.blit(font.render("Gear", True, _GOLD), (rx, card.y + 52))
    gy = card.y + 84
    for kit in data.get("kits") or []:
        locked = bool(kit.get("locked"))
        worn = kit["tier"] == soldier.get("gear_tier")
        label = f"{kit['label']}  {int(kit['cost']):,}c"
        if locked:
            label = f"{kit['label']}  ·  Cmd {kit['command_req']}"
        elif worn:
            label = f"{kit['label']}  ✓ equipped"
        r = pygame.Rect(rx, gy, 400, 34)
        bg = (50, 30, 30) if locked else ((55, 48, 28) if worn else _NAVY2)
        key = f"kit:{kit['tier']}" if not locked and not worn else f"kit_locked:{kit['tier']}"
        _btn(surf, small, rects, key, label, r, bg,
             _MUTED if locked else _TEXT, _BAD if locked else (_GOLD if worn else _GOLD_DIM))
        gy += 40

    # Feedback for kit/train stays visible inside the modal (panel flash is under the veil).
    flash = data.get("flash")
    if flash:
        good = any(k in str(flash) for k in ("Fitted", "Trained", "→", "Equipped", "Outfit"))
        fcol = _OK if good else (_BAD if any(k in str(flash) for k in ("Need", "can't", "Can't", "limit")) else _TEXT)
        fsurf = small.render(str(flash)[:90], True, fcol)
        fr = fsurf.get_rect()
        fr.midtop = (card.centerx, card.y + 48)
        pygame.draw.rect(surf, (20, 24, 36), fr.inflate(16, 8), border_radius=6)
        pygame.draw.rect(surf, fcol, fr.inflate(16, 8), 1, border_radius=6)
        surf.blit(fsurf, fr)

    # Train row under both columns
    ty = max(gy + 12, card.y + 360)
    cost = int(soldier.get("train_cost") or 0)
    surf.blit(font.render("Train (+1 level)", True, _GOLD), (card.x + 24, ty))
    surf.blit(small.render(
        f"{trains_left}/{cap} left  ·  ~{cost:,}c next Att  ·  purse then bank",
        True, _MUTED if trains_left > 0 else _BAD,
    ), (card.x + 200, ty + 4))
    ty += 32
    bx = card.x + 24
    for skill in ("attack", "strength", "defence", "hitpoints"):
        cur = int(lv.get(skill, 1))
        label = f"{skill.title()} {cur}" if trains_left <= 0 else f"{skill.title()} {cur}→{cur + 1}"
        r = pygame.Rect(bx, ty, 165, 40)
        bg = (40, 40, 48) if trains_left <= 0 else (40, 55, 70)
        key = f"train:{skill}" if trains_left > 0 else f"train_cap:{skill}"
        _btn(surf, font, rects, key, label, r, bg, _MUTED if trains_left <= 0 else _TEXT, _GOLD_DIM)
        bx += 175

    up = soldier.get("upgrade")
    bottom_y = card.bottom - 48
    if up:
        locked = bool(up.get("locked"))
        label = (
            f"Need Cmd {up.get('command_req')}"
            if locked
            else f"Promote → {up.get('to_name')}  {int(up.get('cost') or 0):,}c"
        )
        _btn(
            surf, small, rects,
            f"upgrade:{soldier['id']}" if not locked else f"upgrade_locked:{soldier['id']}",
            label,
            pygame.Rect(card.x + 24, bottom_y - 40, 360, 32),
            (50, 30, 30) if locked else (55, 48, 28),
            _MUTED if locked else _SAND,
            _BAD if locked else _GOLD,
        )
    in_realm = bool(data.get("in_castle_realm"))
    if soldier.get("deployed"):
        _btn(
            surf, small, rects, f"recall:{soldier['id']}", "Recall",
            pygame.Rect(card.x + 24, bottom_y, 120, 32),
            (60, 40, 28), _SAND, _GOLD,
        )
    elif in_realm:
        _btn(
            surf, small, rects, f"deploy:{soldier['id']}", "Deploy",
            pygame.Rect(card.x + 24, bottom_y, 120, 32),
            (40, 70, 45), _OK, _OK,
        )
    else:
        surf.blit(small.render("Enter Castle Realm to deploy", True, _MUTED),
                  (card.x + 24, bottom_y + 8))
    _btn(surf, small, rects, f"dismiss:{soldier['id']}", "Dismiss",
         pygame.Rect(card.right - 140, bottom_y, 116, 32), (60, 28, 28), _TEXT, _BAD)


def _draw_practice(client, surf, font, small, body, data, rects, scroll):
    result = data.get("practice_result")
    y = body.y + 10 - scroll
    list_w = body.w - 28
    if result:
        banner = (
            f"{'Victory' if result.get('won') else 'Defeat'} vs {result.get('foe_name')} — "
            f"+{result.get('command_xp')} Command"
            + (f", +{result.get('coins'):,}c" if result.get("coins") else "")
            + (" · Mythos ore!" if result.get("mythos_ore") else "")
        )
        col = _OK if result.get("won") else _BAD
        surf.blit(font.render(banner, True, col), (body.x + 16, y))
        y += 28

    daily = data.get("daily_fights") or {}
    remaining = int(daily.get("remaining", 10))
    cap = int(daily.get("cap", 10))
    surf.blit(small.render(
        f"Your army CL {data.get('roster_total_cl', 0)}  ·  Foes field 10 (5 front / 5 rear)  ·  "
        f"{remaining}/{cap} fights left today",
        True, _MUTED if remaining > 0 else _BAD,
    ), (body.x + 16, y))
    y += 28

    for foe in data.get("practice") or []:
        row = pygame.Rect(body.x + 10, y, list_w, 80)
        if row.bottom < body.y or row.top > body.bottom:
            y += 88
            continue
        unlocked = bool(foe.get("unlocked"))
        can_fight = unlocked and remaining > 0
        gap = int(foe.get("power_gap") or 0)
        recommended = unlocked and gap >= 0
        pygame.draw.rect(surf, (32, 36, 50) if unlocked else (28, 28, 34), row, border_radius=8)
        if recommended:
            border = _GOLD
        elif unlocked:
            border = _OK if gap >= 0 else _BAD
        else:
            border = _GOLD_DIM
        pygame.draw.rect(surf, border, row, 2 if recommended else 1, border_radius=8)
        n_soldiers = int(foe.get("foe_soldiers") or 10)
        title = (
            f"T{foe.get('tier')}  {foe.get('name')}  ·  {n_soldiers} soldiers  ·  "
            f"foe CL {foe.get('foe_combat_level')}  ·  rec {foe.get('recommend_cl')}"
        )
        if recommended:
            title += "  ·  recommended"
        surf.blit(font.render(title, True, _TEXT if unlocked else _MUTED), (row.x + 14, row.y + 12))
        advice = foe.get("advice") or ""
        if not unlocked:
            advice = "Beat the previous house to unlock."
        elif remaining <= 0:
            advice = "Daily fight limit reached — come back tomorrow."
        surf.blit(small.render(
            f"{advice}  ·  win +{foe.get('command_xp_win')} Cmd / {int(foe.get('coin_win') or 0):,}c",
            True, _MUTED,
        ), (row.x + 14, row.y + 44))
        if can_fight:
            _btn(surf, font, rects, f"practice:{foe['id']}", "Battle",
                 pygame.Rect(row.right - 126, row.y + 22, 110, 36), (70, 50, 20), _SAND, _GOLD)
        y += 88
