"""First login: a golden trail to Warden Tamsin, an arrow at the screen edge, a minimap pin and a skip button.

The server decides whether any of it shows (WELCOME_STATE.show_path: kit not claimed, tutorial not skipped,
not already geared). The client only draws it, and only in the overworld. The trail is re-pathed whenever
the player changes tile.
"""
import math
import time

import pygame

GUIDE_ID = "warden_tamsin"
LINES = (
    "Click the ground to walk. The arrow keys step one tile.",
    "Follow the golden trail to Warden Tamsin. She has a Bronze kit for you and will explain the basics.",
    "Press H for the full control list. R eats. Space attacks the nearest monster.",
)
GOLD = (255, 214, 110)
GOLD_DEEP = (205, 140, 40)
SKIP_TEXT = "Tutorial skipped. Warden Tamsin stays by the crossroads if you still want your kit."


def start(client):
    """Called once a new character arrives (after the opening comic)."""
    if not getattr(client, "arrival_guide", False):
        return
    client.arrival_guide = False
    for line in LINES:
        client.add_chat(line, color=(255, 220, 150), highlight=True)


def on_state(client, msg):
    client.welcome = {"show_path": bool(msg.get("show_path")), "claimed": bool(msg.get("claimed")),
                      "owed": int(msg.get("owed") or 0), "guide": dict(msg.get("guide") or {})}
    client._welcome_path = None


def _guide_xy(client):
    g = (getattr(client, "welcome", None) or {}).get("guide") or {}
    if g.get("x") is None or g.get("y") is None:
        return None
    return int(g["x"]), int(g["y"])


def visible(client):
    w = getattr(client, "welcome", None)
    return bool(w and w.get("show_path") and getattr(client, "state", None) == "GAME"
                and getattr(client, "player", None) and not getattr(client, "dungeon", None)
                and _guide_xy(client) is not None)


def trail(client):
    """Tiles from the player to a tile beside Tamsin; recomputed only when either end changes."""
    gx, gy = _guide_xy(client)
    px, py = int(client.player["x"]), int(client.player["y"])
    key = (px, py, gx, gy)
    cached = getattr(client, "_welcome_path", None)
    if cached and cached[0] == key:
        return cached[1]
    goals = client.adjacent_goals(gx, gy) or {(gx, gy)}
    path = client.find_path(px, py, goals) or []
    client._welcome_path = (key, path)
    return path


def draw_trail(client, cam_x, cam_y, vis_w, vis_h, tile):
    """Ground layer: glowing breadcrumbs with a pulse running toward Tamsin, and a ring under her."""
    client._welcome_guide_screen = None
    if not visible(client):
        return
    gx, gy = _guide_xy(client)
    now = time.time()
    pts = []
    for x, y in [(int(client.player["x"]), int(client.player["y"]))] + list(trail(client)):
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        pts.append((sx * tile + tile // 2, sy * tile + tile // 2, 0 <= sx <= vis_w and 0 <= sy <= vis_h))
    r = max(3, tile // 7)
    layer_size = r * 6
    for i, (cx, cy, on) in enumerate(pts[1:], start=1):
        if not on:
            continue
        pulse = 0.5 + 0.5 * math.cos(now * 5.0 - i * 0.7)
        dot = pygame.Surface((layer_size, layer_size), pygame.SRCALPHA)
        mid = layer_size // 2
        pygame.draw.ellipse(dot, (*GOLD, int(50 + 60 * pulse)), (mid - r * 3, mid - r * 3 // 2, r * 6, r * 3))
        pygame.draw.ellipse(dot, (*GOLD, int(150 + 100 * pulse)), (mid - r, mid - r // 2, r * 2, r))
        client.screen.blit(dot, (cx - mid, cy - mid))
    sx, sy = client.world_to_view_offset(gx, gy, cam_x, cam_y)
    hx, hy = sx * tile + tile // 2, sy * tile + tile // 2
    on = 0 <= sx <= vis_w and 0 <= sy <= vis_h
    client._welcome_guide_screen = (hx, hy, on, pygame.Rect(0, 0, int(vis_w * tile), int(vis_h * tile)))
    if on:
        ring = pygame.Surface((tile * 2, tile * 2), pygame.SRCALPHA)
        k = 0.5 + 0.5 * math.sin(now * 3.0)
        rr = int(tile * (0.55 + 0.12 * k))
        pygame.draw.ellipse(ring, (*GOLD, int(120 + 100 * k)), (tile - rr, tile - rr // 2 + tile // 3, rr * 2, rr), 3)
        client.screen.blit(ring, (hx - tile, hy - tile))


def _edge_arrow(client, hx, hy, area):
    cx, cy = area.center
    dx, dy = hx - cx, hy - cy
    if dx == 0 and dy == 0:
        return
    margin = 34
    half_w, half_h = area.w / 2 - margin, area.h / 2 - margin
    k = min(half_w / abs(dx) if dx else 1e9, half_h / abs(dy) if dy else 1e9)
    ax, ay = cx + dx * k, cy + dy * k
    ang = math.atan2(dy, dx)
    pulse = 1.0 + 0.12 * math.sin(time.time() * 5)
    size = 16 * pulse
    tip = (ax + math.cos(ang) * size, ay + math.sin(ang) * size)
    left = (ax + math.cos(ang + 2.5) * size, ay + math.sin(ang + 2.5) * size)
    right = (ax + math.cos(ang - 2.5) * size, ay + math.sin(ang - 2.5) * size)
    pygame.draw.polygon(client.screen, GOLD, (tip, left, right))
    pygame.draw.polygon(client.screen, GOLD_DEEP, (tip, left, right), 2)
    label = client.font_tiny.render("Warden Tamsin", True, GOLD)
    lx = int(ax - math.cos(ang) * 22 - label.get_width() / 2)
    ly = int(ay - math.sin(ang) * 22 - label.get_height() / 2)
    lx = max(area.x + 4, min(area.right - label.get_width() - 4, lx))
    ly = max(area.y + 4, min(area.bottom - label.get_height() - 4, ly))
    bg = pygame.Surface((label.get_width() + 8, label.get_height() + 4), pygame.SRCALPHA)
    bg.fill((16, 12, 6, 170))
    client.screen.blit(bg, (lx - 4, ly - 2))
    client.screen.blit(label, (lx, ly))


def draw(client):
    """HUD layer: the banner with the skip button, and the edge arrow while Tamsin is off screen."""
    client._welcome_skip_rect = None
    if not visible(client):
        return
    seen = getattr(client, "_welcome_guide_screen", None)
    if seen and not seen[2]:
        _edge_arrow(client, seen[0], seen[1], seen[3])
    area = seen[3] if seen else client.screen.get_rect()
    text = client.font_small.render("Follow the golden trail to Warden Tamsin for your Bronze kit", True, GOLD)
    skip = client.font_tiny.render("Skip tutorial  X", True, (236, 224, 196))
    w = text.get_width() + skip.get_width() + 48
    box = pygame.Rect(0, 0, w, max(text.get_height(), skip.get_height()) + 14)
    box.midtop = (area.centerx, area.y + 10)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((18, 14, 8, 210))
    client.screen.blit(panel, box.topleft)
    pygame.draw.rect(client.screen, GOLD_DEEP, box, 2, border_radius=6)
    client.screen.blit(text, (box.x + 12, box.centery - text.get_height() // 2))
    sr = pygame.Rect(0, 0, skip.get_width() + 14, skip.get_height() + 6)
    sr.midright = (box.right - 8, box.centery)
    pygame.draw.rect(client.screen, (70, 50, 30), sr, border_radius=5)
    pygame.draw.rect(client.screen, GOLD_DEEP, sr, 1, border_radius=5)
    client.screen.blit(skip, (sr.x + 7, sr.y + 3))
    client._welcome_skip_rect = sr


def draw_minimap_marker(client, rect):
    if not visible(client):
        return
    gx, gy = _guide_xy(client)
    mx, my = client.world_to_minimap(gx, gy, rect)
    k = 0.5 + 0.5 * math.sin(time.time() * 4)
    pygame.draw.circle(client.screen, (30, 20, 6), (mx, my), 6)
    pygame.draw.circle(client.screen, GOLD, (mx, my), 4 + int(k * 1.5))
    pygame.draw.circle(client.screen, (255, 250, 230), (mx, my), 1)


def handle_event(client, event):
    """True when the skip button took the click."""
    if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
        return False
    rect = getattr(client, "_welcome_skip_rect", None)
    if not rect or not rect.collidepoint(event.pos):
        return False
    try:
        client.net.send("WELCOME_SKIP")
    except Exception:
        pass
    if getattr(client, "welcome", None):
        client.welcome["show_path"] = False
    client._welcome_skip_rect = None
    client.add_chat(SKIP_TEXT, color=(255, 220, 150))
    return True
