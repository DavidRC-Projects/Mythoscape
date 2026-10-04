"""ChatGPT mockup HUD plates. Drawn when USE_HUD_MOCKUP_PLATES is on.

Plates are blitted from the pack, scaled from the 2406×1596 artboard onto the
live 1200×800 client. Live text and icons go in the transparent holes.
Clicks use the pack hitboxes. The flat navy HUD stays in hud_v2.py.
"""
import json
import os

import pygame

import hud_v2
from content import ITEMS, INVENTORY_SIZE

_PACK = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "hud_mockup_plates_pack",
))
_FIX = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "fix",
))
_LIVE = (2406, 1596)
_DATA = None
_SURFACES = {}
_NATIVE = {}

_DRAW = (
    "zone",
    "minimap",
    "left_nav",
    "sidebar_inventory",
    "chat",
    "action_bar",
)
_CLICK = tuple(reversed(_DRAW))

_QUICK = {
    "quickchat_hello": "Hello",
    "quickchat_need_help": "Need help",
    "quickchat_group_up": "Group up",
    "quickchat_good_fight": "Good fight",
    "quickchat_thanks": "Thanks",
    "quickchat_goodbye": "Goodbye",
}
# Image-pixel bounds measured on the plate art, not the estimated JSON boxes.
_TABS = {
    "tab_inventory": (12, 318, 112, 402),
    "tab_crafting": (118, 318, 214, 402),
    "tab_gathering": (220, 318, 322, 402),
    "tab_bags": (328, 318, 424, 402),
}
_FOOTER_BOX = {
    "nav_mounts": (14, 938, 102, 1002),
    "nav_pets": (108, 938, 192, 1002),
    "nav_lore": (198, 938, 284, 1002),
    "nav_achievements": (290, 938, 372, 1002),
    "nav_menu": (378, 938, 430, 1002),
}
_EQUIP_BOX = {
    "btn_equip": (14, 840, 120, 916),
    "btn_use": (124, 840, 216, 916),
    "btn_split": (220, 840, 324, 916),
    "btn_drop": (328, 840, 428, 916),
}
_HEADER_BOX = {
    "portrait": (8, 8, 112, 112),
    "player_name": (172, 16, 380, 44),
    "player_level": (140, 48, 210, 74),
    "xp_bar": (214, 52, 356, 70),
    "xp_pct": (360, 46, 420, 74),
    "title": (148, 78, 320, 116),
    "guild": (78, 118, 340, 148),
    "gold": (72, 164, 190, 200),
    "gems": (240, 168, 310, 198),
    "settings": (396, 18, 430, 52),
    "quest_text": (24, 214, 414, 300),
}
_NAV_BOX = {
    "quests": (6, 12, 80, 94),
    "events": (6, 98, 80, 176),
    "party": (6, 178, 80, 256),
    "guild": (6, 258, 80, 342),
    "pvp": (6, 348, 80, 432),
}
_ACTION_CROP = (158, 8, 524, 128)
# The chat plate includes the first action-bar slot on its right edge.
_CHAT_KEEP = 668
_CHAT_NATIVE_W = 729
_STYLES = ("attack", "strength", "defence", "hitpoints", "archery", "eat")
_STYLE_LABEL = {
    "attack": "ATK",
    "strength": "STR",
    "defence": "DEF",
    "hitpoints": "HP",
    "archery": "RNG",
    "eat": "EAT",
}
_NAV_KEYS = {
    "nav_quests": "quests",
    "nav_events": "events",
    "nav_party": "party",
    "nav_guild": "guild",
    "nav_pvp": "pvp",
    "nav_map": "map",
}
INK = (236, 232, 220)
GOLD = (232, 196, 110)
MUTED = (160, 170, 188)


def _load():
    global _DATA
    if _DATA is None:
        with open(os.path.join(_PACK, "meta", "hitboxes.json"), encoding="utf-8") as handle:
            _DATA = json.load(handle)
    return _DATA


def _screen(client):
    _mw, _mh, _sx, sw, sh = hud_v2._layout()
    return sw, sh, sw / _LIVE[0], sh / _LIVE[1]


def _scale(client):
    """One scale so plates keep their shape on the live window."""
    _sw, _sh, sx, sy = _screen(client)
    return min(sx, sy)


def _plate(name):
    return _load()["plates"][name]


def _visible_chat(client):
    """Chat dest with the baked action-slot strip removed."""
    dest = _dest(client, "chat")
    width = max(1, int(dest.w * _CHAT_KEEP / _CHAT_NATIVE_W))
    return pygame.Rect(dest.x, dest.y, width, dest.h)


def _dest(client, name):
    """Screen rect for a plate. Action bar is placed from the chat, not an anchor."""
    sw, sh, _sx, _sy = _screen(client)
    scale = _scale(client)
    spec = _plate(name)
    if name == "sidebar_inventory":
        dw = max(1, int(spec["size_live"][0] * scale))
        dh = max(1, min(sh, int(spec["size_live"][1] * scale)))
        return pygame.Rect(sw - dw, 0, dw, dh)
    if name == "chat":
        dw = max(1, int(1144 * scale))
        dh = max(1, int(520 * scale))
        return pygame.Rect(8, max(0, sh - 8 - dh), dw, dh)
    if name == "action_bar":
        chat = _visible_chat(client)
        side = _dest(client, "sidebar_inventory")
        crop_w = _ACTION_CROP[2] - _ACTION_CROP[0]
        crop_h = _ACTION_CROP[3] - _ACTION_CROP[1]
        dw = max(1, int(514 * scale))
        dh = max(1, int(dw * crop_h / max(1, crop_w)))
        x = chat.right + 16
        room = side.x - 8 - x
        if dw > room:
            dw = max(1, room)
            dh = max(1, int(dw * crop_h / max(1, crop_w)))
        return pygame.Rect(x, max(0, sh - 12 - dh), dw, dh)
    if name == "minimap":
        side = _dest(client, "sidebar_inventory")
        dw = max(1, int(spec["size_live"][0] * scale))
        dh = max(1, int(spec["size_live"][1] * scale))
        x = side.x - 8 - dw
        y = max(0, int(spec["anchor_live"][1] * scale))
        return pygame.Rect(max(0, x), y, dw, dh)
    if name == "left_nav":
        dw = max(1, int(spec["size_live"][0] * scale))
        dh = max(1, int(spec["size_live"][1] * scale))
        y = max(0, int(spec["anchor_live"][1] * scale))
        chat = _dest(client, "chat")
        if y + dh > chat.top - 8:
            dh = max(1, chat.top - 8 - y)
        return pygame.Rect(8, y, dw, dh)
    ax, ay = spec["anchor_live"]
    dw, dh = spec["size_live"]
    return pygame.Rect(int(ax * scale), int(ay * scale), max(1, int(dw * scale)), max(1, int(dh * scale)))


def _native(rel):
    size = _NATIVE.get(rel)
    if size is not None:
        return size
    image = pygame.image.load(os.path.join(_PACK, rel)).convert_alpha()
    _NATIVE[rel] = image.get_size()
    return image.get_size()


def _slot_boxes():
    boxes = {}
    x0, y0, cell_w, cell_h, gap_x, gap_y = 18, 500, 78, 72, 10, 8
    for row in range(5):
        for col in range(5):
            x = x0 + col * (cell_w + gap_x)
            y = y0 + row * (cell_h + gap_y)
            boxes[f"slot_{row}_{col}"] = (x, y, x + cell_w, y + cell_h)
    return boxes


def _action_src_slots():
    return (
        (154, 16, 210, 122),
        (220, 16, 274, 122),
        (282, 16, 336, 122),
        (342, 16, 396, 122),
        (404, 16, 458, 122),
        (466, 16, 520, 122),
    )


def _map_crop(dest, crop, box):
    x0, y0, x1, y1 = crop
    bx0, by0, bx1, by1 = box
    span_w = max(1, x1 - x0)
    span_h = max(1, y1 - y0)
    return pygame.Rect(
        dest.x + int((bx0 - x0) * dest.w / span_w),
        dest.y + int((by0 - y0) * dest.h / span_h),
        max(1, int((bx1 - bx0) * dest.w / span_w)),
        max(1, int((by1 - by0) * dest.h / span_h)),
    )


def _box_for(name, key, box):
    if name != "sidebar_inventory" or not key:
        return box
    for table in (_TABS, _FOOTER_BOX, _EQUIP_BOX):
        if key in table:
            return table[key]
    if key.startswith("slot_") and len(box) == 4:
        x0, y0, x1, y1 = box
        return (x0, y0, x1, y1 + 4)
    return box


def _local(client, name, box, key=None):
    spec = _plate(name)
    dest = _dest(client, name)
    box = _box_for(name, key, box)
    mw, mh = spec.get("size_mockup") or _native(spec["file"])
    x0, y0, x1, y1 = box
    return pygame.Rect(
        dest.x + int(x0 * dest.w / mw),
        dest.y + int(y0 * dest.h / mh),
        max(1, int((x1 - x0) * dest.w / mw)),
        max(1, int((y1 - y0) * dest.h / mh)),
    )


def _nav_layout(client):
    """Map the five painted buttons, then a Map button under them."""
    dest = _dest(client, "left_nav")
    col_w = max(1, int(dest.w * 84 / 104))
    map_h = max(18, int(dest.h * 78 / (436 + 78)))
    art = pygame.Rect(dest.x, dest.y, col_w, max(1, dest.h - map_h - 4))
    rects = {}
    for name, box in _NAV_BOX.items():
        rects[name] = _map_crop(art, (0, 0, 84, 436), box)
    rects["map"] = pygame.Rect(dest.x + 2, art.bottom + 4, max(1, col_w - 4), map_h)
    return art, rects


def _nav_rects(client):
    _art, rects = _nav_layout(client)
    return rects


def _action_rects(client):
    dest = _dest(client, "action_bar")
    return [_map_crop(dest, _ACTION_CROP, box) for box in _action_src_slots()]


def _image(rel, size):
    key = (rel, size)
    cached = _SURFACES.get(key)
    if cached is not None:
        return cached
    path = os.path.join(_PACK, rel)
    if not os.path.isfile(path):
        return None
    image = pygame.image.load(path).convert_alpha()
    if image.get_size() != size:
        image = pygame.transform.smoothscale(image, size)
    _SURFACES[key] = image
    return image


def _blit_clipped(screen, image, at, clip):
    """Blit without drawing pixels outside clip."""
    if image is None or clip.w < 1 or clip.h < 1:
        return
    prev = screen.get_clip()
    screen.set_clip(clip)
    screen.blit(image, at)
    screen.set_clip(prev)


def _blit_plate(client, name, file_key="file"):
    spec = _plate(name)
    dest = _dest(client, name)
    clip = _visible_chat(client) if name == "chat" else dest
    for hole in (spec.get("holes") or {}).values():
        rect = _local(client, name, hole["box"]).clip(clip)
        if rect.w > 1 and rect.h > 1:
            _clear(rect, client.screen)
    image = _image(spec[file_key], dest.size)
    _blit_clipped(client.screen, image, dest.topleft, clip)
    return dest


def _overlay(client, filename, rect):
    """Stretch the overlay sprite to the hitbox. No extra offset."""
    if rect.w < 2 or rect.h < 2:
        return
    path = os.path.join(_FIX, "overlays", filename)
    if not os.path.isfile(path):
        path = os.path.join(_PACK, "overlays", filename)
    if not os.path.isfile(path):
        return
    key = (path, (rect.w, rect.h))
    image = _SURFACES.get(key)
    if image is None:
        image = pygame.image.load(path).convert_alpha()
        if image.get_size() != (rect.w, rect.h):
            image = pygame.transform.smoothscale(image, (rect.w, rect.h))
        _SURFACES[key] = image
    _blit_clipped(client.screen, image, rect.topleft, rect)


def _clip_text(client, font, text, rect, color, align="left"):
    if rect.w < 4 or rect.h < 4:
        return
    surf = font.render(str(text), True, color)
    if surf.get_width() > rect.w - 4 and font is not client.font_tiny:
        surf = client.font_tiny.render(str(text), True, color)
    screen = client.screen
    prev = screen.get_clip()
    screen.set_clip(rect)
    if align == "center":
        x = rect.centerx - surf.get_width() // 2
    else:
        x = rect.x + 2
    y = rect.centery - surf.get_height() // 2
    screen.blit(surf, (x, y))
    screen.set_clip(prev)


def _hit_rect(client, name, key, hit):
    if name == "left_nav":
        nav = _NAV_KEYS.get(hit.get("action"), key)
        return _nav_rects(client).get(nav) or _local(client, name, hit["box"], key)
    if name == "action_bar" and key.startswith("slot_"):
        try:
            index = int(key.split("_")[1]) - 1
        except ValueError:
            index = -1
        rects = _action_rects(client)
        if 0 <= index < len(rects):
            return rects[index]
    rect = _local(client, name, hit["box"], key)
    if name == "chat":
        rect = rect.clip(_visible_chat(client))
    return rect


def _hits(client):
    rows = []
    for name in _CLICK:
        spec = _plate(name)
        for key, hit in (spec.get("hitboxes") or {}).items():
            rows.append((name, key, hit, _hit_rect(client, name, key, hit)))
    return rows


def _hover(client):
    pos = getattr(client, "_plate_mouse", None)
    if pos is None:
        pos = pygame.mouse.get_pos()
    return pos


def draw(client):
    hud_v2.ensure(client)
    if not client.player:
        return
    client.hud_rects = {}
    client.hud_world_rects = {}
    _draw_zone(client)
    _draw_minimap(client)
    _draw_nav(client)
    _draw_sidebar(client)
    _draw_chat(client)
    _draw_actions(client)
    hud_v2._draw_event_banner(client)
    if client.hud_menu:
        hud_v2._draw_menu(client, client.hud_rects)


def _clear(rect, screen):
    pygame.draw.rect(screen, (10, 14, 26), rect)


def _draw_zone(client):
    safe = hud_v2._zone_safe(client)
    dest = _dest(client, "zone")
    rel = "overlays/zone_safe.png" if safe else "overlays/zone_danger.png"
    image = _image(rel, dest.size)
    if image is None:
        image = _image(_plate("zone")["file"], dest.size)
    if image is not None:
        image = image.copy()
        hole = _local(client, "zone", _plate("zone")["holes"]["label"]["box"])
        pygame.draw.rect(image, (0, 0, 0, 0), pygame.Rect(hole.x - dest.x, hole.y - dest.y, hole.w, hole.h))
        client.screen.blit(image, dest.topleft)
    zone = hud_v2._zone(client)
    name = hud_v2.ZONE_NAMES.get(zone, str(zone).replace("_", " ").title())
    hole = _local(client, "zone", _plate("zone")["holes"]["label"]["box"])
    state = "Safe" if safe else "Danger"
    _clip_text(client, client.font_small, name, pygame.Rect(hole.x, hole.y, hole.w, hole.h // 2), INK, align="center")
    _clip_text(
        client, client.font_tiny, state,
        pygame.Rect(hole.x, hole.y + hole.h // 2, hole.w, hole.h // 2),
        hud_v2.SAFE_GREEN if safe else hud_v2.DANGER_RED,
        align="center",
    )


def _draw_minimap(client):
    _blit_plate(client, "minimap")
    hole = _local(client, "minimap", _plate("minimap")["holes"]["map_circle"]["box"])
    if not client.minimap_collapsed:
        client.draw_minimap(plate_rect=hole)
    else:
        client.minimap_rect = hole
    zone = hud_v2._zone(client)
    name = hud_v2.ZONE_NAMES.get(zone, str(zone).replace("_", " ").title())
    px, py = client.player_xy()
    label = _local(client, "minimap", _plate("minimap")["holes"]["location_text"]["box"])
    _clear(label, client.screen)
    _clip_text(client, client.font_tiny, f"{name}  {int(px)}, {int(py)}", label, INK, align="center")


def _draw_nav(client):
    dest = _dest(client, "left_nav")
    art, rects = _nav_layout(client)
    path = os.path.join(_PACK, _plate("left_nav")["file"])
    image = pygame.image.load(path).convert_alpha()
    source = image.subsurface((0, 0, 84, 436))
    scaled = pygame.transform.smoothscale(source, art.size)
    _blit_clipped(client.screen, scaled, art.topleft, dest)
    map_rect = rects["map"]
    pygame.draw.rect(client.screen, (10, 16, 32), map_rect, border_radius=8)
    pygame.draw.rect(client.screen, (70, 78, 110), map_rect, 1, border_radius=8)
    _clip_text(client, client.font_tiny, "Map", map_rect, INK, align="center")
    mx, my = _hover(client)
    safe = hud_v2._zone_safe(client)
    for name, rect in rects.items():
        if name == "pvp" and not safe:
            _overlay(client, "overlay_nav_circle.png", rect)
        elif rect.collidepoint(mx, my):
            _overlay(client, "overlay_nav_circle.png", rect)
        if name == "quests" and hud_v2._current_quest(client):
            pygame.draw.circle(client.screen, GOLD, (rect.right - 6, rect.y + 6), 3)
    client.hud_world_rects["nav"] = rects


def _draw_sidebar(client):
    _blit_plate(client, "sidebar_inventory")
    holes = _plate("sidebar_inventory")["holes"]
    player = client.player or {}
    name = player.get("name") or "Adventurer"
    level = client.player_combat_level()
    frac, _lvl = hud_v2._xp_fraction(client)

    def hole(key):
        return _local(client, "sidebar_inventory", holes[key]["box"])

    _portrait(client, hole("portrait"), name)
    _clip_text(client, client.font_small, name, hole("player_name"), INK)
    _clip_text(client, client.font_tiny, f"Lv {level}", hole("player_level"), GOLD)
    xp = _local(client, "sidebar_inventory", (210, 50, 416, 72))
    _clear(xp, client.screen)
    bar = pygame.Rect(xp.x, xp.centery - 4, int(xp.w * 0.72), 8)
    pygame.draw.rect(client.screen, (24, 32, 48), bar, border_radius=3)
    fill = bar.copy()
    fill.w = max(0, int(bar.w * frac))
    if fill.w:
        pygame.draw.rect(client.screen, GOLD, fill, border_radius=3)
    _clip_text(
        client, client.font_tiny, f"{int(frac * 100)}%",
        pygame.Rect(bar.right + 2, xp.y, max(8, xp.right - bar.right - 2), xp.h),
        MUTED, align="center",
    )
    block = _local(client, "sidebar_inventory", (40, 100, 340, 158))
    _clear(block, client.screen)
    _clip_text(
        client, client.font_tiny, hud_v2._title(client),
        pygame.Rect(block.x, block.y, block.w, block.h // 2), GOLD, align="center",
    )
    _clip_text(
        client, client.font_tiny, "No guild",
        pygame.Rect(block.x + 28, block.y + block.h // 2, block.w - 28, block.h // 2), MUTED,
    )
    coins = int(player.get("coins") or 0)
    _clip_text(client, client.font_small, f"{coins:,}", hole("gold"), GOLD)
    _clip_text(client, client.font_small, str(hud_v2._gem_count(client)), hole("gems"), (140, 190, 255))
    quest = hole("quest_text")
    _quest_text(client, quest)
    cap = hole("inv_capacity")
    filled = len(hud_v2._inventory_entries(client))
    _clip_text(client, client.font_tiny, f"{filled} / {INVENTORY_SIZE}", cap, MUTED, align="center")
    _draw_tab_labels(client)
    _draw_equip_labels(client)
    _draw_sidebar_body(client, holes)
    _sidebar_overlays(client)


def _draw_tab_labels(client):
    """The capacity punch removes the ends of the Gathering and Bags labels."""
    hole = _plate("sidebar_inventory")["holes"].get("inv_capacity")
    if hole:
        _clear(_local(client, "sidebar_inventory", hole["box"]), client.screen)
    for key, word in (("tab_gathering", "Gathering"), ("tab_bags", "Bags")):
        rect = _local(client, "sidebar_inventory", (0, 0, 0, 0), key)
        band = pygame.Rect(rect.x + 2, rect.y + int(rect.h * 0.55), rect.w - 4, rect.h - int(rect.h * 0.55) - 2)
        _clear(band, client.screen)
        _clip_text(client, client.font_tiny, word, band, INK, align="center")


def _draw_equip_labels(client):
    labels = (
        ((28, 877, 109, 906), "Equip"),
        ((128, 877, 209, 906), "Use"),
        ((228, 877, 309, 906), "Split"),
        ((328, 877, 409, 906), "Drop"),
    )
    for box, word in labels:
        rect = _local(client, "sidebar_inventory", box)
        _clear(rect, client.screen)
        _clip_text(client, client.font_tiny, word, rect, INK, align="center")


def _portrait(client, rect, name):
    pygame.draw.circle(client.screen, (28, 36, 58), rect.center, min(rect.w, rect.h) // 2)
    pygame.draw.circle(client.screen, GOLD, rect.center, min(rect.w, rect.h) // 2, 2)
    letter = (name[:1] or "A").upper()
    surf = client.font.render(letter, True, INK)
    client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))


def _quest_text(client, rect):
    quest = hud_v2._current_quest(client)
    screen = client.screen
    prev = screen.get_clip()
    screen.set_clip(rect)
    if not quest:
        _clip_text(client, client.font_small, "No active quest", rect, MUTED)
    else:
        qname, desc, progress, need, status = quest
        _clip_text(client, client.font_small, qname, pygame.Rect(rect.x, rect.y, rect.w, 18), INK)
        detail = f"{progress}/{need}" if need else status.replace("_", " ")
        _clip_text(client, client.font_tiny, detail, pygame.Rect(rect.x, rect.y + 18, rect.w, 16), GOLD)
        if desc:
            _clip_text(client, client.font_tiny, desc, pygame.Rect(rect.x, rect.y + 34, rect.w, 16), MUTED)
    screen.set_clip(prev)


def _draw_sidebar_body(client, holes):
    focus = client.hud_focus
    grid = _grid_rect(client, holes)
    if focus or client.hud_system != "inventory":
        pygame.draw.rect(client.screen, (10, 14, 26), grid.inflate(4, 4), border_radius=6)
    if focus == "lore":
        hud_v2._draw_lore(client, grid.y, grid.bottom)
        return
    if focus == "achievements":
        hud_v2._draw_achievements(client, grid.y, grid.bottom)
        return
    if focus in ("mounts", "party", "guild", "events"):
        messages = {
            "mounts": "No mounts yet.",
            "party": "You are not in a party.",
            "guild": "You are not in a guild.",
            "events": "No world event is active.",
        }
        _clip_text(client, client.font_small, messages[focus], grid, MUTED)
        return
    system = client.hud_system
    if system == "inventory":
        _draw_slots(client, holes)
    elif system == "crafting":
        _draw_rows(client, grid, (
            ("forge", "Forge", "Smelt and smith"),
            ("fletch", "Fletching", "Bows and arrows"),
            ("cook", "Cooking", "Cook food"),
            ("alchemy", "Alchemy", "Combat potions"),
        ), "stations")
    elif system == "gathering":
        _draw_gather(client, grid)
    else:
        _draw_bag_rows(client, grid)


def _grid_rect(client, holes):
    first = _local(client, "sidebar_inventory", holes["slot_0_0"]["box"], "slot_0_0")
    last = _local(client, "sidebar_inventory", holes["slot_4_4"]["box"], "slot_4_4")
    return first.union(last)


def _draw_slots(client, holes):
    import procedural_sprites_finished as sprites
    rows = hud_v2._filtered_entries(client)
    slots = {}
    hits = _plate("sidebar_inventory")["hitboxes"]
    mx, my = _hover(client)
    for row in range(5):
        for col in range(5):
            key = f"slot_{row}_{col}"
            hit = hits.get(key)
            if not hit:
                continue
            rect = _local(client, "sidebar_inventory", hit["box"], key)
            _clear(rect, client.screen)
    for index, (slot, entry) in enumerate(rows[:25]):
        col, row = index % 5, index // 5
        key = f"slot_{row}_{col}"
        hit = hits.get(key)
        if not hit:
            break
        rect = _local(client, "sidebar_inventory", hit["box"], key)
        sprites.draw_item_icon(client.screen, rect.inflate(-8, -8), entry["item_id"], ITEMS)
        if int(entry.get("qty") or 1) > 1:
            qty = client.font_tiny.render(str(entry["qty"]), True, GOLD)
            client.screen.blit(qty, (rect.right - qty.get_width() - 2, rect.bottom - qty.get_height()))
        if slot == client.hud_selected or rect.collidepoint(mx, my):
            _overlay(client, "overlay_slot_roundrect.png", rect)
        slots[slot] = rect
    client.hud_rects["slots"] = slots


def _draw_rows(client, grid, rows, key):
    boxes = {}
    y = grid.y + 4
    for name, title, blurb in rows:
        if y + 36 > grid.bottom:
            break
        rect = pygame.Rect(grid.x + 4, y, grid.w - 8, 34)
        state = hud_v2._station_state(client, name) if key == "stations" else ""
        pygame.draw.rect(client.screen, (18, 24, 40), rect, border_radius=6)
        _clip_text(client, client.font_small, title, pygame.Rect(rect.x, rect.y, rect.w // 2, 18), INK)
        _clip_text(client, client.font_tiny, blurb, pygame.Rect(rect.x, rect.y + 16, rect.w - 8, 16), MUTED)
        if state:
            _clip_text(client, client.font_tiny, state, pygame.Rect(rect.right - 70, rect.y + 6, 66, 16), GOLD, align="center")
        boxes[name] = rect
        y += 38
    client.hud_rects[key] = boxes


def _draw_gather(client, grid):
    y = grid.y + 4
    for skill in ("mining", "woodcutting", "fishing"):
        if y + 32 > grid.bottom:
            break
        y += hud_v2._skill_bar(client, skill, grid.x + 6, y, grid.w - 16)
        y += 4
    walk = {}
    labels = (("mining", "Mine"), ("woodcutting", "Chop"), ("fishing", "Fish"))
    width = max(40, (grid.w - 16) // 3)
    for i, (key, label) in enumerate(labels):
        rect = pygame.Rect(grid.x + 4 + i * width, grid.bottom - 28, width - 4, 24)
        pygame.draw.rect(client.screen, (18, 24, 40), rect, border_radius=5)
        _clip_text(client, client.font_tiny, label, rect, INK, align="center")
        walk[key] = rect
    client.hud_rects["gather"] = walk


def _draw_bag_rows(client, grid):
    boxes = {}
    y = grid.y + 4
    player = client.player or {}
    for label, flag, total_key, cap in hud_v2.BAG_ROWS:
        if y + 24 > grid.bottom:
            break
        owned = bool(player.get(flag))
        total = int(player.get(total_key) or 0)
        rect = pygame.Rect(grid.x + 4, y, grid.w - 8, 22)
        pygame.draw.rect(client.screen, (18, 24, 40), rect, border_radius=4)
        detail = f"{label}  {total}/{cap}" if owned else f"{label}  —"
        _clip_text(client, client.font_tiny, detail, rect, INK if owned else MUTED)
        boxes[label] = rect
        y += 24
    client.hud_rects["bags"] = boxes


def _sidebar_overlays(client):
    mx, my = _hover(client)
    hits = _plate("sidebar_inventory")["hitboxes"]
    for key, hit in hits.items():
        action = hit.get("action")
        rect = _local(client, "sidebar_inventory", hit["box"], key)
        selected_tab = (
            (action == "sys_inventory" and client.hud_system == "inventory" and not client.hud_focus)
            or (action == "sys_crafting" and client.hud_system == "crafting")
            or (action == "sys_gathering" and client.hud_system == "gathering")
            or (action == "sys_bags" and client.hud_system == "bags")
        )
        if selected_tab or (action and action.startswith("sys_") and rect.collidepoint(mx, my)):
            _overlay(client, "overlay_tab_roundrect.png", rect)
        elif action in ("open_mounts", "open_pets", "open_lore", "open_achievements", "open_menu"):
            if rect.collidepoint(mx, my):
                _overlay(client, "overlay_footer_roundrect.png", rect)
        elif action in ("inv_equip", "inv_use", "inv_split", "inv_drop") and rect.collidepoint(mx, my):
            _overlay(client, "overlay_tab_roundrect.png", rect)
    utility = {}
    for name, action in (
        ("mounts", "open_mounts"),
        ("pets", "open_pets"),
        ("lore", "open_lore"),
        ("achievements", "open_achievements"),
        ("menu", "open_menu"),
    ):
        for hit_key, hit in hits.items():
            if hit.get("action") == action:
                utility[name] = _local(client, "sidebar_inventory", hit["box"], hit_key)
    client.hud_rects["utility"] = utility


def _draw_chat(client):
    _blit_plate(client, "chat")
    hole = _local(client, "chat", _plate("chat")["holes"]["messages"]["box"])
    _clear(hole, client.screen)
    lines = hud_v2._visible_lines(client)
    screen = client.screen
    prev = screen.get_clip()
    screen.set_clip(hole)
    line_h = 15
    visible = max(1, hole.h // line_h)
    y = hole.y + 2
    for line in lines[-visible:]:
        color = line.get("color") or hud_v2.CHANNEL_COLOR.get(line.get("channel") or "system", INK)
        surf = client.font_tiny.render(str(line.get("text") or ""), True, color)
        screen.blit(surf, (hole.x + 2, y))
        y += line_h
    screen.set_clip(prev)
    field = _local(client, "chat", _plate("chat")["hitboxes"]["input"]["box"])
    field.y -= 8
    field.h += 8
    field = field.clip(_visible_chat(client))
    _clear(field, client.screen)
    prompt = client.chat_text if client.chat_typing else "Type a message..."
    _clip_text(client, client.font_tiny, prompt, field, INK if client.chat_typing else MUTED)
    mx, my = _hover(client)
    tabs = {}
    for key, hit in _plate("chat")["hitboxes"].items():
        action = hit.get("action") or ""
        rect = _local(client, "chat", hit["box"])
        if action.startswith("chat_tab_"):
            channel = action.replace("chat_tab_", "")
            tabs[channel] = rect
            if client.hud_channel == channel or rect.collidepoint(mx, my):
                _overlay(client, "overlay_tab_roundrect.png", rect)
        elif rect.collidepoint(mx, my) and action.startswith("quickchat_"):
            _overlay(client, "overlay_tab_roundrect.png", rect)
    client.hud_rects["channels"] = tabs
    client.hud_rects["chat_input"] = _local(client, "chat", _plate("chat")["hitboxes"]["input"]["box"])


def _action_image():
    cached = _SURFACES.get("action-restored")
    if cached is not None:
        return cached
    path = os.path.join(_PACK, _plate("action_bar")["file"])
    image = pygame.image.load(path).convert_alpha()
    width, height = image.get_size()
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = image.get_at((x, y))
            if alpha != 255:
                image.set_at((x, y), (red, green, blue, 255))
    _SURFACES["action-restored"] = image
    return image


def _draw_actions(client):
    dest = _dest(client, "action_bar")
    pygame.draw.rect(client.screen, (10, 14, 26), dest, border_radius=10)
    image = _action_image()
    x0, y0, x1, y1 = _ACTION_CROP
    source = image.subsurface((x0, y0, x1 - x0, y1 - y0))
    scaled = pygame.transform.smoothscale(source, dest.size)
    _blit_clipped(client.screen, scaled, dest.topleft, dest)
    mx, my = _hover(client)
    style = getattr(client, "combat_style", None)
    rects = {}
    for index, key in enumerate(_STYLES):
        rect = _action_rects(client)[index]
        if key == style or rect.collidepoint(mx, my):
            _overlay(client, "overlay_slot_roundrect.png", rect)
        rects[key] = rect
    client.hud_world_rects["actions"] = rects


def handle_click(client, mx, my, button):
    hud_v2.ensure(client)
    rects = client.hud_rects or {}
    if client.hud_menu:
        if rects.get("menu_logout") and rects["menu_logout"].collidepoint(mx, my):
            client.hud_menu = False
            client.logout()
            return True
        if rects.get("menu_help") and rects["menu_help"].collidepoint(mx, my):
            client.hud_menu = False
            client.show_help = True
            client.help_scroll = 0
            return True
        client.hud_menu = False
        return True
    event = (client.hud_world_rects or {}).get("event") or {}
    join = event.get("join")
    if join and join.collidepoint(mx, my):
        place = (event.get("event") or {}).get("location")
        client.add_chat("No world event to join." if not place else f"Head toward {place}.")
        return True
    for name, key, hit, rect in _hits(client):
        if not rect.collidepoint(mx, my):
            continue
        action = hit.get("action")
        if action == "inv_slot" and (client.hud_system != "inventory" or client.hud_focus):
            break
        _dispatch(client, action, hit, button)
        return True
    if client.hud_system == "crafting" and not client.hud_focus:
        for key, rect in (rects.get("stations") or {}).items():
            if rect.collidepoint(mx, my):
                hud_v2._station_click(client, key)
                return True
    if client.hud_system == "gathering" and not client.hud_focus:
        for key, rect in (rects.get("gather") or {}).items():
            if rect.collidepoint(mx, my):
                hud_v2._gather_click(client, key)
                return True
    return False


def _dispatch(client, action, hit, button):
    if action == "open_equipment":
        client.show_equipment = not client.show_equipment
        return
    if action == "open_settings":
        client.show_help = not client.show_help
        if client.show_help:
            client.help_scroll = 0
        return
    if action == "open_quests":
        client.hud_focus = None
        client.add_chat("Quest progress is on the sidebar card.")
        return
    if action in ("sys_inventory", "sys_crafting", "sys_gathering", "sys_bags"):
        client.hud_system = action.replace("sys_", "")
        client.hud_focus = None
        return
    if action in ("inv_equip", "inv_use", "inv_split", "inv_drop"):
        hud_v2._inventory_action(client, action.replace("inv_", ""))
        return
    if action == "inv_slot":
        slot = _slot_at(client, int(hit.get("index") or 0))
        if slot is None:
            return
        if button == 3 or client.hud_selected == slot:
            hud_v2._activate_slot(client, slot, button if button == 3 else 1)
        else:
            client.hud_selected = slot
        return
    if action in ("open_mounts", "open_pets", "open_lore", "open_achievements", "open_menu"):
        hud_v2._utility_click(client, action.replace("open_", ""))
        return
    nav = _NAV_KEYS.get(action)
    if nav:
        hud_v2._nav_click(client, nav)
        return
    if action in ("open_map", "open_zone_info"):
        if action == "open_map":
            client.toggle_world_map()
        else:
            zone = hud_v2._zone(client)
            name = hud_v2.ZONE_NAMES.get(zone, str(zone).replace("_", " ").title())
            state = "safe" if hud_v2._zone_safe(client) else "dangerous"
            client.add_chat(f"{name} is {state}.")
        return
    if action and action.startswith("chat_tab_"):
        client.hud_channel = action.replace("chat_tab_", "")
        return
    phrase = _QUICK.get(action)
    if phrase:
        client.net.send("CHAT", text=phrase)
        client.add_chat(f"You: {phrase}", color=hud_v2.CHANNEL_COLOR["world"])
        return
    if action == "chat_focus":
        client.chat_typing = True
        return
    if action == "chat_send":
        if client.chat_text.strip():
            client.net.send("CHAT", text=client.chat_text.strip())
        client.chat_typing = False
        client.chat_text = ""
        return


def _slot_at(client, index):
    rows = hud_v2._filtered_entries(client)
    if index < 0 or index >= len(rows) or index >= 25:
        return None
    return rows[index][0]
