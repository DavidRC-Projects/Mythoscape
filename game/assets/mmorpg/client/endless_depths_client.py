"""Endless Depths mouth, theme room plates, and HUD overlay."""
from __future__ import annotations

import math
import os
import time

import pygame

import world_map as wm

_PATH = os.path.join(os.path.dirname(__file__), "assets", "endless_depths", "mouth.png")
_THEMES = os.path.join(os.path.dirname(__file__), "assets", "endless_depths", "themes")
MOUTH = (11, 21)
_cache = {}
# Theme plates that need a readability lift under hazard washes.
_DARK_THEMES = frozenset({"shadow", "demonic", "catacomb", "cosmic"})


def active(client):
    d = getattr(client, "dungeon", None) or {}
    return d.get("id") == "endless_depths"


def _extra(client):
    return (getattr(client, "dungeon", None) or {}).get("endless_depths") or {}


def _sprite():
    mtime = 0.0
    try:
        mtime = os.path.getmtime(_PATH)
    except OSError:
        pass
    hit = _cache.get("img")
    if hit is not None and _cache.get("mtime") == mtime:
        return hit
    if not os.path.isfile(_PATH):
        _cache["img"] = None
        _cache["mtime"] = mtime
        return None
    try:
        img = pygame.image.load(_PATH).convert_alpha()
    except Exception:
        img = None
    _cache.clear()
    _cache["img"] = img
    _cache["mtime"] = mtime
    return img


def _scaled(tile, height_tiles):
    img = _sprite()
    if img is None:
        return None
    key = ("scaled", tile, height_tiles)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    h = max(8, int(tile * height_tiles))
    w = max(8, int(img.get_width() * (h / img.get_height())))
    surf = pygame.transform.smoothscale(img, (w, h))
    _cache[key] = surf
    return surf


def _theme_plate(art, pixel_w, pixel_h):
    key = ("theme_px", art, pixel_w, pixel_h)
    hit = _cache.get(key)
    if hit is not None or key in _cache:
        return hit
    path = os.path.join(_THEMES, f"{art}.png")
    if not os.path.isfile(path):
        _cache[key] = None
        return None
    try:
        raw = pygame.image.load(path).convert()
    except Exception:
        _cache[key] = None
        return None
    surf = pygame.transform.smoothscale(raw, (max(8, int(pixel_w)), max(8, int(pixel_h))))
    _cache[key] = surf
    return surf


def _portal_glow(screen, cx, cy, tile, t):
    pulse = 0.55 + 0.45 * math.sin(t * 2.6)
    for i, (mul, alpha) in enumerate(((2.3, 50), (1.6, 85), (1.05, 130))):
        r = max(6, int(tile * mul * (0.85 + 0.15 * pulse)))
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        colour = (255, 160 + i * 18, 60 + i * 10, int(alpha * (0.7 + 0.3 * pulse)))
        pygame.draw.circle(glow, colour, (r, r), r)
        screen.blit(glow, (cx - r, cy - int(tile * 1.5) - r), special_flags=pygame.BLEND_ADD)


def draw_mouth(screen, cx, cy, tile, t=None):
    if t is None:
        t = time.time()
    _portal_glow(screen, cx, cy, tile, t)
    surf = _scaled(tile, 5.0)
    if surf is None:
        return cy - tile
    rect = surf.get_rect()
    rect.midbottom = (cx, cy + tile // 5)
    screen.blit(surf, rect)
    rim = max(10, tile // 2)
    pygame.draw.ellipse(
        screen, (255, 190, 90),
        pygame.Rect(cx - rim, cy - int(tile * 1.65), rim * 2, max(8, tile)),
        2,
    )
    return rect.top


def draw_exit(screen, cx, cy, tile):
    """Plain text marker — no mouth/portal art on the leave tile."""
    label = _font(max(14, tile // 2), True).render("exit", True, (255, 220, 90))
    # Soft dark plate behind the word so it stays readable on every theme.
    pad_x, pad_y = 8, 4
    plate = pygame.Surface(
        (label.get_width() + pad_x * 2, label.get_height() + pad_y * 2),
        pygame.SRCALPHA,
    )
    plate.fill((12, 10, 16, 180))
    pr = plate.get_rect(center=(cx, cy - tile // 8))
    screen.blit(plate, pr)
    pygame.draw.rect(screen, (255, 200, 80), pr, 1)
    screen.blit(label, label.get_rect(center=pr.center))
    return True


def draw_room_backdrop(client, cam_x, cam_y, tile):
    """Stretch the theme plate across the full map panel + chat strip — no letterbox."""
    if not active(client):
        return False
    art = _extra(client).get("art") or _extra(client).get("theme") or "crypt"
    try:
        import client as client_mod
        panel_w = int(getattr(client_mod, "MAP_W", 900))
        panel_h = int(getattr(client_mod, "MAP_H", 640))
        screen_h = int(getattr(client_mod, "SCREEN_H", panel_h + 80))
    except Exception:
        panel_w, panel_h, screen_h = 900, 640, 720
    # Always cover the entire game panel (and chat column) so the room reads
    # as full-screen even when 22×40 tiles leave a few pixels of MAP_W unused.
    px_w = max(panel_w, 8)
    px_h = max(screen_h, 8)
    plate = _theme_plate(art, px_w, px_h)
    if plate is None:
        return False
    client.screen.blit(plate, (0, 0))
    # Shadow / demonic plates are near-black — lift them so hazards stay readable.
    if art in _DARK_THEMES:
        lift = pygame.Surface((px_w, px_h), pygame.SRCALPHA)
        lift.fill((55, 48, 70, 70) if art == "shadow" else (45, 35, 40, 55))
        client.screen.blit(lift, (0, 0))
    return True


def _font(size, bold=False):
    try:
        return pygame.font.SysFont("georgia", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def _paint_door_tile(client, rect, open_, t, boss=False):
    """Opaque door plate with yellow (or crimson boss) rim."""
    plate = pygame.Surface(rect.size, pygame.SRCALPHA)
    if open_:
        if boss:
            plate.fill((36, 10, 14, 235))
        else:
            plate.fill((28, 18, 10, 230))
        client.screen.blit(plate, rect.topleft)
        pulse = 0.55 + 0.45 * math.sin((t or 0) * 3.2)
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        if boss:
            glow.fill((255, int(70 + 40 * pulse), 70, int(100 + 40 * pulse)))
        else:
            glow.fill((255, int(170 + 50 * pulse), 60, int(90 + 40 * pulse)))
        client.screen.blit(glow, rect.topleft)
    else:
        plate.fill((22, 18, 28, 235) if not boss else (30, 12, 18, 235))
        client.screen.blit(plate, rect.topleft)
    pulse = 0.5 + 0.5 * math.sin((t or 0) * 4.0)
    if boss:
        rim = (255, int(90 + 50 * pulse), 90) if not open_ else (255, 160, 140)
    else:
        rim = (255, int(160 + 60 * pulse), 40) if not open_ else (255, 220, 120)
    pygame.draw.rect(client.screen, rim, rect.inflate(-max(2, rect.w // 8), -max(2, rect.h // 8)), 2)


def _door_label_text(open_, boss=False, remaining=0):
    if open_:
        return "Boss next" if boss else "Next level"
    if remaining > 0:
        return "Clear foes"
    return "Sealed"


def _queue_door_label(client, rect, wx, open_, door_xs, boss=False, remaining=0):
    """Remember label placement — painted after all door plates so nothing clips it."""
    xs = sorted(door_xs)
    if not xs:
        return
    mid_x = (xs[0] + xs[-1]) / 2.0
    cx = rect.centerx - (int(wx) - mid_x) * rect.w
    cy = rect.centery
    client._endless_door_label = {
        "cx": cx,
        "cy": cy,
        "open": bool(open_),
        "boss": bool(boss),
        "text": _door_label_text(open_, boss=boss, remaining=remaining),
        "tile_w": rect.w,
        "tile_h": rect.h,
        "count": len(xs),
    }


def flush_door_label(client):
    """Draw the deferred door-state label on top of the door plates."""
    info = getattr(client, "_endless_door_label", None)
    client._endless_door_label = None
    if not info or not active(client):
        return
    open_ = bool(info.get("open"))
    boss = bool(info.get("boss"))
    text = info.get("text") or _door_label_text(open_, boss=boss)
    if boss and open_:
        col = (255, 180, 160)
    elif open_:
        col = (255, 230, 140)
    else:
        col = (210, 185, 120)
    tile_h = max(8, int(info.get("tile_h") or 40))
    count = max(1, int(info.get("count") or 3))
    tile_w = max(8, int(info.get("tile_w") or 40))
    max_w = tile_w * count - 6
    f = _font(max(13, tile_h // 2), True)
    surf = f.render(text, True, col)
    if surf.get_width() > max_w:
        f = _font(max(11, tile_h // 3), True)
        surf = f.render(text, True, col)
    # Dark plate behind the full phrase so theme pixels never eat glyphs.
    pad_x, pad_y = 6, 2
    plate = pygame.Surface(
        (surf.get_width() + pad_x * 2, surf.get_height() + pad_y * 2),
        pygame.SRCALPHA,
    )
    plate.fill((12, 10, 16, 200))
    pr = plate.get_rect(center=(int(info["cx"]), int(info["cy"])))
    client.screen.blit(plate, pr)
    if boss:
        rim = (255, 140, 120) if open_ else (180, 80, 70)
    else:
        rim = (255, 220, 120) if open_ else (200, 160, 70)
    pygame.draw.rect(client.screen, rim, pr, 1)
    client.screen.blit(surf, surf.get_rect(center=pr.center))


def draw_tile(client, rect, tile_id, wx, wy, t):
    if not active(client):
        return False
    extra = _extra(client)
    door = {(int(p[0]), int(p[1])) for p in (extra.get("door") or []) if len(p) >= 2}
    on_door = (int(wx), int(wy)) in door
    if on_door:
        open_ = bool(extra.get("door_open"))
        # Boss telegraph colours the *next* door when this floor is a boss floor
        # still sealed, or the open door after a boss clear (walk to next).
        floor = int(extra.get("floor") or 1)
        boss_here = bool(extra.get("boss_floor"))
        boss_next = ((floor + 1) % 10 == 0) if open_ else boss_here
        remaining = int(extra.get("remaining") or 0)
        _paint_door_tile(client, rect, open_, t, boss=boss_next or boss_here)
        xs = sorted({p[0] for p in door})
        # Queue from the last door tile in left→right paint order so placement
        # uses a finished rect; the label itself is flushed after the tile pass.
        if xs and int(wx) == xs[-1]:
            _queue_door_label(
                client, rect, int(wx), open_, xs,
                boss=boss_next, remaining=remaining,
            )
        return True
    if tile_id == wm.WALL:
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        veil.fill((12, 10, 16, 50))
        client.screen.blit(veil, rect.topleft)
        return True
    return True


def _panel(surf, rect, edge=(210, 160, 70)):
    pygame.draw.rect(surf, (18, 14, 22, 210), rect, border_radius=8)
    pygame.draw.rect(surf, edge, rect, 2, border_radius=8)


_HAZARD_TINT = {
    "poison": (40, 160, 50, 55),
    "fire": (220, 80, 20, 50),
    "freeze": (80, 160, 230, 55),
    # Darkness must stay playable — old 120α + broken MIN vignette blacked the room.
    "darkness": (8, 4, 18, 48),
    "roots": (50, 100, 40, 45),
}

def draw_hazard_fx(client, map_w, map_h):
    """Full-panel environmental wash while a floor hazard is active."""
    if not active(client):
        return
    hazard = _extra(client).get("hazard")
    tint = _HAZARD_TINT.get(hazard)
    if not tint:
        return
    now = time.time()
    pulse = 0.75 + 0.25 * math.sin(now * (2.2 if hazard != "darkness" else 1.1))
    if hazard == "darkness":
        # Soft edge vignette only — never a full-screen blackout.
        try:
            import client as client_mod
            tile = int(getattr(client_mod, "TILE", 40))
        except Exception:
            tile = 40
        cx, cy = map_w // 2, map_h // 2
        vignette = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        # Ring of darkness at the borders; centre stays clear for combat.
        max_a = int(70 * pulse)
        for i in range(8):
            a = int(max_a * (i + 1) / 8)
            inset = int(tile * (0.4 + i * 0.35))
            pygame.draw.rect(
                vignette, (0, 0, 0, a),
                pygame.Rect(0, 0, map_w, map_h),
                max(2, inset // 2),
            )
        # Mild cool wash so the hazard still reads without hiding entities.
        wash = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        wash.fill((8, 4, 22, int(28 * pulse)))
        client.screen.blit(wash, (0, 0))
        client.screen.blit(vignette, (0, 0))
        return
    veil = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
    r, g, b, a = tint
    veil.fill((r, g, b, int(a * pulse)))
    client.screen.blit(veil, (0, 0))


def draw_overlay(client, map_w=None, map_h=None):
    """Compact corner HUD — floor, depth meter, foes, door/hazard."""
    if not active(client):
        return
    try:
        import client as client_mod
        map_w = map_w or int(getattr(client_mod, "MAP_W", 900))
        map_h = map_h or int(getattr(client_mod, "MAP_H", 640))
    except Exception:
        map_w = map_w or 900
        map_h = map_h or 640
    # Door label is queued during the tile pass; paint it now so side plates
    # cannot clip "Next level".
    flush_door_label(client)
    draw_hazard_fx(client, map_w, map_h)
    ex = _extra(client)
    floor = int(ex.get("floor") or 1)
    remaining = int(ex.get("remaining") or 0)
    door_open = bool(ex.get("door_open"))
    theme = (ex.get("theme") or "crypt").title()
    hazard_label = ex.get("hazard_label")
    group_size = int(ex.get("group_size") or 1)
    run_cleared = int(ex.get("run_cleared") or 0)
    best = int(ex.get("best") or ex.get("highest") or 0)
    boss = bool(ex.get("boss_floor"))

    lines = 4 + (1 if hazard_label else 0) + (1 if group_size > 1 else 0) + (1 if boss else 0)
    box_h = 8 + lines * 14 + 4
    r = pygame.Rect(8, 8, 168, box_h)
    edge = (220, 90, 80) if boss else (210, 160, 70)
    _panel(client.screen, r, edge=edge)
    f = _font(12, True)
    f_sm = _font(11)
    y = r.y + 4
    title = f"Fl. {floor} · {theme}"
    if boss:
        title = f"Fl. {floor} · BOSS"
    client.screen.blit(f.render(title, True, (255, 220, 120) if not boss else (255, 170, 150)), (r.x + 7, y))
    y += 14
    # Depth meter — floors cleared this run vs personal best.
    meter = f"Run {run_cleared}  ·  Best {best}"
    client.screen.blit(f_sm.render(meter, True, (180, 210, 255)), (r.x + 7, y))
    y += 13
    rem_col = (255, 120, 100) if remaining else (140, 230, 140)
    client.screen.blit(f_sm.render(f"{remaining} foes", True, rem_col), (r.x + 7, y))
    y += 13
    door_txt = "Door OPEN" if door_open else "Door sealed"
    door_col = (255, 210, 90) if door_open else (180, 140, 120)
    client.screen.blit(f_sm.render(door_txt, True, door_col), (r.x + 7, y))
    y += 13
    if hazard_label:
        client.screen.blit(f_sm.render(hazard_label, True, (255, 140, 110)), (r.x + 7, y))
        y += 13
    if group_size > 1:
        client.screen.blit(f_sm.render(f"Party ×{group_size}", True, (160, 210, 255)), (r.x + 7, y))
        y += 13
    if boss:
        client.screen.blit(f_sm.render("Champion waits", True, (255, 130, 110)), (r.x + 7, y))

    # Leave sits beside the panel so it doesn't cover the floor line.
    leave = pygame.Rect(r.right + 4, r.y, 44, 18)
    client.dungeon_leave_rect = leave
    client.dungeon_hud_hide_rect = None
    client.dungeon_hud_tab = None
    pygame.draw.rect(client.screen, (90, 40, 35), leave, border_radius=3)
    pygame.draw.rect(client.screen, (220, 100, 80), leave, 1, border_radius=3)
    lt = f_sm.render("Leave", True, (255, 255, 255))
    client.screen.blit(lt, (leave.centerx - lt.get_width() // 2, leave.centery - lt.get_height() // 2))

    hint = _font(12).render("South EXIT leaves", True, (220, 210, 180))
    client.screen.blit(hint, hint.get_rect(midbottom=(map_w // 2, map_h - 8)))
    draw_banner(client, map_w, map_h)


def handle_click(client, tx, ty):
    extra = _extra(client)
    door = {(int(p[0]), int(p[1])) for p in (extra.get("door") or []) if len(p) >= 2}
    if (int(tx), int(ty)) not in door:
        return False
    # Door tiles are always FLOOR — walk onto them. on_step / interact advances
    # once the chamber is cleared (door_open).
    goals = {(int(tx), int(ty))}
    client.walk_and_act(goals, {"type": "DUNGEON_INTERACT", "x": int(tx), "y": int(ty)})
    return True


# --------------------------------------------------------------------------- centre banners (boss / milestone / PB / theme)
_BANNER_EDGE = {
    "boss": (220, 90, 80),
    "milestone": (210, 160, 70),
    "pb": (120, 200, 255),
    "theme": (160, 210, 140),
}


def open_banner(client, msg):
    """Centre flash from ENDLESS_BANNER."""
    until = float(msg.get("until") or (time.time() + 3.0))
    client.endless_banner = {
        "kind": str(msg.get("kind") or "milestone"),
        "title": str(msg.get("title") or ""),
        "subtitle": str(msg.get("subtitle") or ""),
        "until": until,
    }


def draw_banner(client, map_w, map_h):
    banner = getattr(client, "endless_banner", None)
    if not banner:
        return
    if time.time() >= float(banner.get("until") or 0):
        client.endless_banner = None
        return
    title = banner.get("title") or ""
    if not title:
        return
    kind = banner.get("kind") or "milestone"
    edge = _BANNER_EDGE.get(kind, (210, 160, 70))
    remaining = max(0.0, float(banner.get("until") or 0) - time.time())
    alpha = 230 if remaining > 0.6 else int(230 * remaining / 0.6)
    box_w = min(map_w - 40, 420)
    box = pygame.Rect(0, 0, box_w, 72 if banner.get("subtitle") else 52)
    box.center = (map_w // 2, max(70, map_h // 5))
    plate = pygame.Surface(box.size, pygame.SRCALPHA)
    plate.fill((14, 10, 18, alpha))
    client.screen.blit(plate, box.topleft)
    pygame.draw.rect(client.screen, edge, box, 2, border_radius=8)
    t = _font(22, True).render(title, True, (255, 230, 180))
    client.screen.blit(t, t.get_rect(midtop=(box.centerx, box.y + 10)))
    sub = banner.get("subtitle") or ""
    if sub:
        s = _font(13).render(sub, True, (200, 190, 170))
        client.screen.blit(s, s.get_rect(midtop=(box.centerx, box.y + 40)))


# --------------------------------------------------------------------------- entry prompt (continue vs start over)
def open_entry_prompt(client, msg):
    """Show continue / start-over modal from ENDLESS_ENTRY_PROMPT."""
    floor = max(2, int(msg.get("continue_floor") or 2))
    theme = (msg.get("theme_label") or msg.get("theme") or theme_name(floor)).title()
    client.endless_entry_prompt = {
        "continue_floor": floor,
        "theme": theme,
        "hazard_label": msg.get("hazard_label"),
        "hazard_tip": msg.get("hazard_tip"),
        "boss_floor": bool(msg.get("boss_floor")),
        "highest": int(msg.get("highest") or 0),
        "solo_highest": int(msg.get("solo_highest") or 0),
        "t0": time.time(),
    }
    client.endless_entry_rects = {}


def theme_name(floor):
    themes = (
        "crypt", "catacomb", "frozen", "toxic", "volcanic",
        "demonic", "shadow", "forest", "dragon", "cosmic",
    )
    n = max(1, int(floor))
    return themes[(n - 1) % len(themes)]


def entry_prompt_active(client):
    return bool(getattr(client, "endless_entry_prompt", None))


def close_entry_prompt(client):
    client.endless_entry_prompt = None
    client.endless_entry_rects = {}


def draw_entry_prompt(client):
    prompt = getattr(client, "endless_entry_prompt", None)
    if not prompt:
        return
    sw, sh = client.screen.get_size()
    # Dim the world behind the choice.
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((4, 3, 8, 160))
    client.screen.blit(veil, (0, 0))

    floor = int(prompt.get("continue_floor") or 2)
    theme = prompt.get("theme") or "Crypt"
    haz = prompt.get("hazard_label")
    tip = prompt.get("hazard_tip")
    boss = bool(prompt.get("boss_floor"))
    best = max(int(prompt.get("highest") or 0), int(prompt.get("solo_highest") or 0))
    extra_lines = (1 if haz else 0) + (1 if tip else 0) + (1 if boss else 0) + (1 if best else 0)
    box = pygame.Rect(0, 0, 440, 210 + extra_lines * 18)
    box.center = (sw // 2, sh // 2 - 20)
    pygame.draw.rect(client.screen, (18, 14, 22), box, border_radius=10)
    pygame.draw.rect(client.screen, (210, 160, 70), box, 2, border_radius=10)

    title = _font(20, True).render("Endless Depths", True, (255, 220, 120))
    client.screen.blit(title, title.get_rect(midtop=(box.centerx, box.y + 16)))
    body = _font(14).render(
        f"You reached floor {floor} ({theme}).", True, (230, 220, 200),
    )
    client.screen.blit(body, body.get_rect(midtop=(box.centerx, box.y + 52)))
    y = box.y + 78
    if best:
        b = _font(12).render(f"Personal best: floor {best}", True, (180, 210, 255))
        client.screen.blit(b, b.get_rect(midtop=(box.centerx, y)))
        y += 18
    if boss:
        b = _font(12, True).render("Boss floor waiting ahead.", True, (255, 150, 130))
        client.screen.blit(b, b.get_rect(midtop=(box.centerx, y)))
        y += 18
    if haz:
        h = _font(12).render(f"Hazard: {haz}", True, (255, 140, 110))
        client.screen.blit(h, h.get_rect(midtop=(box.centerx, y)))
        y += 18
    if tip:
        t = _font(11).render(str(tip), True, (200, 170, 150))
        client.screen.blit(t, t.get_rect(midtop=(box.centerx, y)))
        y += 18
    ask = _font(13).render(
        "Continue from there, or start over at floor 1?", True, (190, 180, 160),
    )
    client.screen.blit(ask, ask.get_rect(midtop=(box.centerx, y)))

    btn_w, btn_h = 170, 36
    cont = pygame.Rect(0, 0, btn_w, btn_h)
    fresh = pygame.Rect(0, 0, btn_w, btn_h)
    cancel = pygame.Rect(0, 0, 100, 30)
    cont.topleft = (box.x + 40, box.bottom - 88)
    fresh.topright = (box.right - 40, box.bottom - 88)
    cancel.midbottom = (box.centerx, box.bottom - 14)

    client.endless_entry_rects = {
        "box": box, "continue": cont, "fresh": fresh, "cancel": cancel,
    }

    def _btn(rect, fill, edge, label, colour=(255, 255, 255)):
        pygame.draw.rect(client.screen, fill, rect, border_radius=6)
        pygame.draw.rect(client.screen, edge, rect, 1, border_radius=6)
        t = _font(13, True).render(label, True, colour)
        client.screen.blit(t, t.get_rect(center=rect.center))

    _btn(cont, (70, 50, 20), (255, 200, 80), f"Continue (Fl. {floor})", (255, 235, 160))
    _btn(fresh, (40, 55, 70), (140, 180, 220), "Start over", (220, 235, 255))
    _btn(cancel, (50, 35, 35), (160, 100, 90), "Cancel", (230, 200, 190))


def handle_entry_prompt_click(client, mx, my):
    prompt = getattr(client, "endless_entry_prompt", None)
    if not prompt:
        return False
    rects = getattr(client, "endless_entry_rects", None) or {}
    cont = rects.get("continue")
    fresh = rects.get("fresh")
    cancel = rects.get("cancel")
    box = rects.get("box")
    if cont and cont.collidepoint(mx, my):
        close_entry_prompt(client)
        client.net.send(
            "ENTER_DUNGEON",
            dungeon_id="endless_depths",
            endless_mode="continue",
        )
        return True
    if fresh and fresh.collidepoint(mx, my):
        close_entry_prompt(client)
        client.net.send(
            "ENTER_DUNGEON",
            dungeon_id="endless_depths",
            endless_mode="fresh",
        )
        return True
    if cancel and cancel.collidepoint(mx, my):
        close_entry_prompt(client)
        return True
    if box and not box.collidepoint(mx, my):
        close_entry_prompt(client)
        return True
    return True  # swallow clicks while open


def handle_entry_prompt_key(client, event):
    if not entry_prompt_active(client):
        return False
    if event.key == pygame.K_ESCAPE:
        close_entry_prompt(client)
        return True
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_c):
        close_entry_prompt(client)
        client.net.send(
            "ENTER_DUNGEON",
            dungeon_id="endless_depths",
            endless_mode="continue",
        )
        return True
    if event.key in (pygame.K_1, pygame.K_KP1, pygame.K_s):
        close_entry_prompt(client)
        client.net.send(
            "ENTER_DUNGEON",
            dungeon_id="endless_depths",
            endless_mode="fresh",
        )
        return True
    return True
