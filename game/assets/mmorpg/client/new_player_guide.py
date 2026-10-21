"""First login: a golden trail to Warden Tamsin, an arrow at the screen edge, a minimap pin and a skip button.

The server decides whether any of it shows (WELCOME_STATE.show_path: kit not claimed, tutorial not skipped,
not already geared). The client only draws it, and only in the overworld. The trail is re-pathed whenever
the player changes tile.

Stage 2 — after the Bronze kit is claimed, the banner and trail move on to Elder Miriam (NW cottage) and her
"Rat Problem" quest, the first thing every new player should do. Once any quest is underway, guidance retires
and the sidebar quest card takes over. Everything still obeys WELCOME_STATE.show_path / skipped, so veterans
and players who skipped the tutorial see none of it.

Also draws a small key-hints chip (H/M/B/E/Tab) under the banner, so the most useful controls are always
one glance away for new players.
"""
import math
import time

import pygame

from content import QUESTS

GUIDE_ID = "warden_tamsin"
NEXT_NPC_ID = "elder_miriam"          # stage 2 target: the starter quest giver
NEXT_NPC_NAME = "Elder Miriam"
LINES = (
    "Click the ground to walk. The arrow keys step one tile.",
    "Follow the golden trail to Warden Tamsin. She has a Bronze kit for you and will explain the basics.",
    "Press H for the full control list. R eats. Space attacks the nearest monster.",
)
LINES_STAGE2 = (
    "Kit equipped! Now visit Elder Miriam in the north-west cottage for your first quest.",
    "The golden trail will lead you to her cottage door.",
)
LINES_DONE = (
    "Quest started — you're on your own from here. Press H any time for controls.",
    "The minimap (M) marks shops, dungeons and your home.",
)
GOLD = (255, 214, 110)
GOLD_DEEP = (205, 140, 40)
SKIP_TEXT = "Tutorial skipped. Warden Tamsin stays by the crossroads if you still want your kit."
SKIP_TEXT2 = "Tutorial skipped. Elder Miriam is still in the north-west cottage if you want a quest."
DONE_TEXT = "Kit equipped! Check the sidebar for your stats — press H any time for controls."
HINT_KEYS = (("H", "Controls"), ("M", "Map"), ("B", "Bank"), ("E", "Gear"), ("Tab", "Skills"))


def start(client):
    """Called once a new character arrives (after the opening comic)."""
    if not getattr(client, "arrival_guide", False):
        return
    client.arrival_guide = False
    for line in LINES:
        client.add_chat(line, color=(255, 220, 150), highlight=True)


def on_state(client, msg):
    prev_claimed = bool((getattr(client, "welcome", None) or {}).get("claimed"))
    prev_quest = _quest_underway(client)
    client.welcome = {"show_path": bool(msg.get("show_path")), "claimed": bool(msg.get("claimed")),
                      "owed": int(msg.get("owed") or 0), "guide": dict(msg.get("guide") or {})}
    client._welcome_path = None
    if getattr(client, "state", None) != "GAME" or not client.welcome.get("show_path"):
        return
    # Kit just claimed: announce stage 2 once.
    if client.welcome["claimed"] and not prev_claimed:
        client._welcome_path = None
        for line in LINES_STAGE2:
            client.add_chat(line, color=(255, 220, 150), highlight=True)
    # First quest just started: tutorial complete.
    elif prev_claimed and not prev_quest and _quest_underway(client):
        for line in LINES_DONE:
            client.add_chat(line, color=(255, 220, 150), highlight=True)


def _guide_xy(client):
    g = (getattr(client, "welcome", None) or {}).get("guide") or {}
    if g.get("x") is None or g.get("y") is None:
        return None
    return int(g["x"]), int(g["y"])


def _npc_xy(client, npc_id):
    """First NPC matching id, from the client's world state."""
    for npc in getattr(client, "npcs", None) or []:
        if npc.get("id") == npc_id and npc.get("x") is not None:
            return int(npc["x"]), int(npc["y"])
    return None


def _quest_underway(client):
    for state in (getattr(client, "quests", None) or {}).values():
        if state and (state.get("status") or "not_started") not in ("complete", "not_started"):
            return True
    return False


def _stage(client):
    """('tamsin', xy) until the kit is claimed, then ('miriam', xy) until a quest is underway."""
    w = getattr(client, "welcome", None) or {}
    if not w.get("claimed"):
        return "tamsin", _guide_xy(client)
    if _quest_underway(client):
        return None, None
    return "miriam", _npc_xy(client, NEXT_NPC_ID)


def visible(client):
    w = getattr(client, "welcome", None)
    if not (w and w.get("show_path") and getattr(client, "state", None) == "GAME"
            and getattr(client, "player", None) and not getattr(client, "dungeon", None)):
        return False
    # The character creator opens over the world on first login and takes every
    # event. Drawing the tutorial banner on top of it put a Skip button on
    # screen that could not be clicked — the first thing a new player tries.
    # Stay hidden until the creator is closed.
    outfitters = getattr(client, "outfitters", None)
    if outfitters is not None and getattr(outfitters, "active", False):
        return False
    # _stage() returning a stage name is not enough: stage 2 needs Elder Miriam
    # to be in the loaded NPC list, which is empty until WORLD_STATE arrives.
    # Without a target there is nothing to point at, so stay hidden.
    _kind, target = _stage(client)
    return target is not None


def trail(client):
    """Tiles from the player to the current guide target; recomputed only when either end changes."""
    _kind, target = _stage(client)
    if target is None:
        return []
    gx, gy = target
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
    """Ground layer: glowing breadcrumbs with a pulse running toward the guide target, and a ring under them."""
    client._welcome_guide_screen = None
    if not visible(client):
        return
    _kind, target = _stage(client)
    gx, gy = target
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


def _edge_arrow(client, hx, hy, area, label, colour=GOLD):
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
    pygame.draw.polygon(client.screen, colour, (tip, left, right))
    pygame.draw.polygon(client.screen, GOLD_DEEP, (tip, left, right), 2)
    label = client.font_tiny.render(label, True, colour)
    lx = int(ax - math.cos(ang) * 22 - label.get_width() / 2)
    ly = int(ay - math.sin(ang) * 22 - label.get_height() / 2)
    lx = max(area.x + 4, min(area.right - label.get_width() - 4, lx))
    ly = max(area.y + 4, min(area.bottom - label.get_height() - 4, ly))
    bg = pygame.Surface((label.get_width() + 8, label.get_height() + 4), pygame.SRCALPHA)
    bg.fill((16, 12, 6, 170))
    client.screen.blit(bg, (lx - 4, ly - 2))
    client.screen.blit(label, (lx, ly))


def _banner_line(client):
    kind, _target = _stage(client)
    if kind == "miriam":
        return f"Kit claimed — follow the trail to {NEXT_NPC_NAME} for your first quest"
    return "Follow the golden trail to Warden Tamsin for your Bronze kit"


def draw(client):
    """HUD layer: the banner with the skip button, the edge arrow while the target is off screen, and key hints."""
    client._welcome_skip_rect = None
    client._welcome_hints_rect = None
    if not visible(client):
        return
    kind, _target = _stage(client)
    seen = getattr(client, "_welcome_guide_screen", None)
    if seen and not seen[2]:
        _edge_arrow(client, seen[0], seen[1], seen[3],
                    NEXT_NPC_NAME if kind == "miriam" else "Warden Tamsin")
    area = seen[3] if seen else client.screen.get_rect()
    text = client.font_small.render(_banner_line(client), True, GOLD)
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
    _draw_key_hints(client, box)


def _draw_key_hints(client, banner_box):
    """Small chip under the banner: the five most useful keys, always on screen for new players."""
    chips = []
    for key, name in HINT_KEYS:
        k = client.font_tiny.render(key, True, GOLD)
        n = client.font_tiny.render(name, True, (200, 190, 170))
        chips.append((k, n, k.get_width() + n.get_width() + 18))
    pad, gap, chip_h = 12, 10, 26
    total = sum(c[2] for c in chips) + gap * (len(chips) - 1) + pad * 2
    chip_box = pygame.Rect(0, 0, total, chip_h)
    chip_box.midtop = (banner_box.centerx, banner_box.bottom + 8)
    panel = pygame.Surface(chip_box.size, pygame.SRCALPHA)
    panel.fill((18, 14, 8, 190))
    client.screen.blit(panel, chip_box.topleft)
    pygame.draw.rect(client.screen, (120, 96, 52), chip_box, 1, border_radius=6)
    x = chip_box.x + pad
    for k, n, w in chips:
        client.screen.blit(k, (x, chip_box.centery - k.get_height() // 2))
        client.screen.blit(n, (x + k.get_width() + 5, chip_box.centery - n.get_height() // 2))
        x += w + gap
    client._welcome_hints_rect = chip_box


def draw_minimap_marker(client, rect):
    if not visible(client):
        return
    _kind, target = _stage(client)
    if target is None:
        return
    mx, my = client.world_to_minimap(target[0], target[1], rect)
    k = 0.5 + 0.5 * math.sin(time.time() * 4)
    onscreen = rect.collidepoint(mx, my)
    if not onscreen:
        # The guide is usually out of view on first login: pin it to the rim
        # with an arrow so "follow the trail" has a direction on the map too.
        if hasattr(client, "_minimap_rim_point"):
            mx, my, ang = client._minimap_rim_point(target[0], target[1], rect)
            if hasattr(client, "_draw_minimap_rim_pin"):
                client._draw_minimap_rim_pin(mx, my, ang, GOLD)
                return
    pygame.draw.circle(client.screen, (30, 20, 6), (mx, my), 6)
    pygame.draw.circle(client.screen, GOLD, (mx, my), 4 + int(k * 1.5))
    pygame.draw.circle(client.screen, (255, 250, 230), (mx, my), 1)


def handle_event(client, event):
    """True when the skip button took the click (or the X key, handled by the client)."""
    if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
        return False
    rect = getattr(client, "_welcome_skip_rect", None)
    if not rect or not rect.collidepoint(event.pos):
        return False
    _do_skip(client)
    return True


def skip_key(client):
    """Called by the client when the X key is pressed while the guide is visible."""
    if visible(client):
        _do_skip(client)
        return True
    return False


def _do_skip(client):
    kind, _target = _stage(client)
    try:
        client.net.send("WELCOME_SKIP")
    except Exception:
        pass
    if getattr(client, "welcome", None):
        client.welcome["show_path"] = False
    client._welcome_skip_rect = None
    client._welcome_hints_rect = None
    client.add_chat(SKIP_TEXT2 if kind == "miriam" else SKIP_TEXT, color=(255, 220, 150))


# ---------------------------------------------------------------------------
# Wayfinding — a pointer to whatever you are trying to reach.
#
# The tutorial already rings Warden Tamsin and Elder Miriam. A new player's next
# questions are "where is the shop?", "where do I hand this quest in?" and
# "which way is the bank?" — and the answer should not require opening a map.
# This draws a small labelled arrow at the edge of the view toward the nearest
# thing you are looking for, plus a rim pin on the corner minimap.
# ---------------------------------------------------------------------------

# Short labels keep the pointer readable at a glance.
FACILITY_LABELS = {
    "bank": "Bank", "forge": "Smithy", "furnace": "Furnace", "anvil": "Anvil",
    "range": "Cooking fire", "fireplace": "Hearth", "shop": "Shop", "market": "Market",
}
WAYPOINT_COLOR = (120, 200, 255)
QUEST_COLOR = (255, 214, 110)


def nearest_interactable(client, kinds):
    """Closest interactable of the given kind(s), measured from the player."""
    try:
        px, py = client.player_xy()
    except Exception:
        return None
    best, best_d = None, None
    for spot in getattr(client, "interactables", None) or []:
        if spot.get("kind") not in kinds or spot.get("x") is None:
            continue
        d = max(abs(int(spot["x"]) - int(px)), abs(int(spot["y"]) - int(py)))
        if best_d is None or d < best_d:
            best, best_d = spot, d
    return (int(best["x"]), int(best["y"]), best) if best else None


def quest_turnin_npc(client):
    """The NPC to return to for the active quest, if one is ready to hand in."""
    for qid, state in (getattr(client, "quests", None) or {}).items():
        if not state or (state.get("status") or "") != "ready":
            continue
        spec = QUESTS.get(qid) or {}
        giver = spec.get("giver")
        for npc in getattr(client, "npcs", None) or []:
            if npc.get("id") == giver and npc.get("x") is not None:
                return int(npc["x"]), int(npc["y"]), npc.get("name") or "Quest giver"
    return None


def waypoint_target(client):
    """(x, y, label, colour) for the one place worth pointing at right now.

    Priority: a quest ready to hand in, then the waypoint you set yourself,
    then the tutorial guide. Shops and facilities are opt-in (nav clicks).
    """
    turnin = quest_turnin_npc(client)
    if turnin:
        return turnin[0], turnin[1], f"Hand in: {turnin[2]}", QUEST_COLOR
    mine = getattr(client, "nav_waypoint", None)
    if mine:
        return mine[0], mine[1], mine[2] or "Waypoint", WAYPOINT_COLOR
    if visible(client):
        kind, target = _stage(client)
        if target is not None:
            name = NEXT_NPC_NAME if kind == "miriam" else "Warden Tamsin"
            return target[0], target[1], name, GOLD
    return None


def set_waypoint(client, wx, wy, label):
    client.nav_waypoint = (int(wx), int(wy), str(label or "Waypoint")[:24])
    client.add_chat(f"Waypoint set: {client.nav_waypoint[2]}. An arrow at the screen edge points the way.",
                    color=WAYPOINT_COLOR)
    client._welcome_path = None


def clear_waypoint(client):
    if getattr(client, "nav_waypoint", None):
        client.nav_waypoint = None
        client.add_chat("Waypoint cleared.", color=WAYPOINT_COLOR)


def draw_waypoint(client, cam_x, cam_y, vis_w, vis_h, tile, area=None):
    """Edge arrow toward the active waypoint / quest turn-in, unless it is on screen.

    Called right after draw_trail, which already knows the camera and view size.
    """
    target = waypoint_target(client)
    if not target or getattr(client, "dungeon", None):
        return
    wx, wy, label, colour = target
    try:
        px, py = client.player_xy()
    except Exception:
        return
    if int(px) == int(wx) and int(py) == int(wy):
        return
    sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
    if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
        return  # already visible — walking to it is obvious
    if area is None:
        area = pygame.Rect(0, 0, int(vis_w * tile), int(vis_h * tile))
    _edge_arrow(client, sx * tile + tile // 2, sy * tile + tile // 2, area, label, colour)


def draw_waypoint_minimap(client, rect):
    """Rim pin on the corner minimap for the active waypoint."""
    target = waypoint_target(client)
    if not target or getattr(client, "dungeon", None):
        return
    wx, wy, label, colour = target
    mx, my = client.world_to_minimap(wx, wy, rect)
    if rect.collidepoint(mx, my):
        return
    if hasattr(client, "_minimap_rim_point") and hasattr(client, "_draw_minimap_rim_pin"):
        rx, ry, ang = client._minimap_rim_point(wx, wy, rect)
        client._draw_minimap_rim_pin(rx, ry, ang, colour)
