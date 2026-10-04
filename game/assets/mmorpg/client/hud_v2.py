"""Navy / gold HUD chrome. Drawn only when USE_NEW_HUD is on.

World rendering, networking, and inventory rules stay in client.py. This module
paints the sidebar, chat, left nav, zone chip, and action bar, and forwards
clicks to the existing equip / use / forge / cook handlers.
"""
import pygame

import combat
from content import (
    ITEMS, QUESTS, SKILL_DISPLAY_NAMES, STORAGE_BAG_IDS, INVENTORY_SIZE,
    is_gem_item, is_storage_bag,
)

NAVY = (12, 18, 34)
NAVY_CARD = (20, 28, 48)
NAVY_HI = (32, 42, 68)
GOLD = (212, 175, 90)
GOLD_DIM = (120, 96, 52)
INK = (232, 226, 210)
MUTED = (150, 160, 180)
SAFE_GREEN = (72, 180, 110)
DANGER_RED = (210, 70, 70)

SAFE_ZONES = {"village", "city", "fishing_village"}
ZONE_NAMES = {
    "fishing_village": "Harbourreach",
    "city": "Stonehaven",
    "shadow_crypt": "Void Sanctum",
    "volcano": "Emberdeep",
    "dungeon": "Dungeon",
    "wilderness": "Wilderness",
    "village": "Village",
    "forest": "Forest",
    "mountains": "Mountains",
    "mine": "Mine",
}

SYSTEMS = (
    ("inventory", "Inventory"),
    ("crafting", "Crafting"),
    ("gathering", "Gathering"),
    ("bags", "Bags"),
)
FILTERS = (
    ("all", "All"),
    ("weapons", "Weapons"),
    ("armour", "Armour"),
    ("consumables", "Consumables"),
    ("materials", "Materials"),
    ("quest", "Quest"),
)
CHANNELS = ("all", "world", "guild", "party", "whisper")
CHANNEL_COLOR = {
    "world": (140, 190, 255),
    "guild": (120, 210, 150),
    "party": (240, 190, 90),
    "whisper": (210, 160, 255),
    "system": (160, 170, 185),
}
QUICK = ("Hello", "Group up", "Thanks", "Need help", "Good fight")
BAG_ROWS = (
    ("Food Bag", "has_food_bag", "food_bag_total", 200),
    ("Raw Food", "has_raw_bag", "raw_bag_total", 200),
    ("Mining Bag", "has_mining_bag", "mining_bag_total", 200),
    ("Log Bag", "has_log_bag", "log_bag_total", 200),
    ("Gem Bag", "has_gem_bag", "gem_bag_total", 200),
    ("Potion Pouch", "has_potion_pouch", "potion_pouch_total", 200),
    ("Fletching Pouch", "has_fletch_pouch", "fletch_pouch_total", 200),
    ("Tip Box", "has_tip_box", "tip_box_total", 200),
)


def _layout():
    """Screen metrics from the running client module. Never import client.py."""
    import sys
    for name in ("__main__", "client"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "MAP_W"):
            return mod.MAP_W, mod.MAP_H, mod.SIDEBAR_X, mod.SCREEN_W, mod.SCREEN_H
    return 900, 640, 900, 1200, 800


def ensure(client):
    if getattr(client, "_hud_ready", False):
        return
    client._hud_ready = True
    client.hud_system = "inventory"
    client.hud_filter = "all"
    client.hud_selected = None
    client.hud_inv_scroll = 0
    client.hud_inv_max_scroll = 0
    client.hud_channel = "all"
    client.hud_pvp_mode = False
    client.hud_menu = False
    client.hud_focus = None
    client.hud_rects = {}
    client.hud_world_rects = {}


def _panel(surf, rect, fill=NAVY_CARD, border=GOLD_DIM, radius=8, width=1):
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, width, border_radius=radius)


def _text(client, font, text, color):
    return font.render(str(text), True, color)


def _blit(client, font, text, xy, color=INK):
    surf = _text(client, font, text, color)
    client.screen.blit(surf, xy)
    return surf


def _zone(client):
    import world_map as wm
    px, py = client.player_xy()
    return wm.get_zone(int(px), int(py))


def _zone_safe(client):
    if getattr(client, "hud_pvp_mode", False):
        return False
    if client.dungeon:
        return False
    return _zone(client) in SAFE_ZONES


def _xp_fraction(client):
    xp_map = (client.player or {}).get("xp") or {}
    total = int(xp_map.get("hitpoints") or 0)
    level = combat.level_from_xp(total)
    cur = combat.xp_for_level(level)
    nxt = combat.xp_for_level(level + 1)
    span = max(1, nxt - cur)
    return max(0.0, min(1.0, (total - cur) / span)), level


def _title(client):
    best = None
    best_pts = -1
    for qid, state in (client.quests or {}).items():
        if (state or {}).get("status") != "complete":
            continue
        spec = QUESTS.get(qid) or {}
        pts = int(spec.get("quest_points") or 0)
        if pts > best_pts:
            best_pts = pts
            best = spec.get("name") or qid
    return best or "Adventurer"


def _current_quest(client):
    for qid, state in (client.quests or {}).items():
        status = (state or {}).get("status") or "not_started"
        if status in ("complete", "not_started"):
            continue
        spec = QUESTS.get(qid) or {}
        progress = int((state or {}).get("progress") or 0)
        need = int(spec.get("count") or 0)
        return spec.get("name") or qid, spec.get("description") or "", progress, need, status
    return None


def _item_bucket(item_id):
    item = ITEMS.get(item_id) or {}
    slot = item.get("equip_slot")
    kind = item.get("type") or ""
    if slot == "weapon" or kind == "weapon":
        return "weapons"
    if slot in ("helmet", "body", "legs", "shield", "cape", "ammo"):
        return "armour"
    if kind in ("food", "potion") or item.get("heal") or item.get("boost_skill"):
        return "consumables"
    if kind in ("gem", "ore", "bar", "log") or item.get("tool_for"):
        return "materials"
    if kind == "quest" or item.get("quest_item"):
        return "quest"
    return "other"


def _inventory_entries(client):
    inv = (client.player or {}).get("inventory") or {}
    rows = []
    for key, entry in inv.items():
        if not entry or not entry.get("item_id"):
            continue
        try:
            slot = int(key)
        except (TypeError, ValueError):
            continue
        rows.append((slot, entry))
    rows.sort(key=lambda pair: pair[0])
    return rows


def _filtered_entries(client):
    filt = getattr(client, "hud_filter", "all")
    rows = []
    for slot, entry in _inventory_entries(client):
        item_id = entry.get("item_id")
        if is_storage_bag(item_id):
            continue
        if filt != "all" and _item_bucket(item_id) != filt:
            continue
        rows.append((slot, entry))
    return rows


def _gem_count(client):
    total = 0
    for _slot, entry in _inventory_entries(client):
        if is_gem_item(entry.get("item_id")):
            total += int(entry.get("qty") or 0)
    bag = (client.player or {}).get("gem_bag") or {}
    if isinstance(bag, dict):
        total += sum(int(v or 0) for v in bag.values())
    return total


def _activate_slot(client, slot, button):
    """Run the existing inventory click handler against one slot."""
    rects = client.hud_rects.get("slots") or {}
    rect = rects.get(slot)
    if rect is None:
        return
    original = client.inventory_slot_rects

    def only_this():
        return {slot: rect}

    client.inventory_slot_rects = only_this
    try:
        client.handle_inventory_click(rect.centerx, rect.centery, button)
    finally:
        client.inventory_slot_rects = original


def _selected_entry(client):
    slot = getattr(client, "hud_selected", None)
    if slot is None or not client.player:
        return None, None
    inv = client.player.get("inventory") or {}
    entry = inv.get(str(slot)) or inv.get(slot)
    return slot, entry


def draw_world_chrome(client):
    """Left nav, zone chip, action bar, and an event banner over the world."""
    ensure(client)
    if not client.player:
        return
    _draw_zone_chip(client)
    _draw_left_nav(client)
    _draw_action_bar(client)
    _draw_event_banner(client)


def _draw_zone_chip(client):
    if client.dungeon:
        client.hud_world_rects["zone"] = None
        return
    zone = _zone(client)
    name = ZONE_NAMES.get(zone, str(zone).replace("_", " ").title())
    safe = _zone_safe(client)
    label = "Safe Zone" if safe else "PvP Danger"
    title = _text(client, client.font_small, name, INK)
    sub = _text(client, client.font_tiny, label, SAFE_GREEN if safe else DANGER_RED)
    width = max(title.get_width(), sub.get_width()) + 36
    rect = pygame.Rect(8, 8, width, 36)
    _panel(client.screen, rect, NAVY, SAFE_GREEN if safe else DANGER_RED, radius=8, width=2)
    pygame.draw.circle(client.screen, SAFE_GREEN if safe else DANGER_RED, (rect.x + 14, rect.centery), 5)
    client.screen.blit(title, (rect.x + 26, rect.y + 2))
    client.screen.blit(sub, (rect.x + 26, rect.y + 18))
    client.hud_world_rects["zone"] = rect


def _draw_left_nav(client):
    labels = ("Quests", "Events", "Party", "Guild", "Map", "PvP")
    keys = ("quests", "events", "party", "guild", "map", "pvp")
    top = 52
    rects = {}
    safe = _zone_safe(client)
    for i, (key, label) in enumerate(zip(keys, labels)):
        rect = pygame.Rect(8, top + i * 46, 52, 42)
        active = key == "pvp" and (not safe)
        border = DANGER_RED if active else GOLD
        _panel(client.screen, rect, NAVY, border, radius=8, width=2 if active else 1)
        mark = _text(client, client.font_tiny, label[:1], GOLD if not active else DANGER_RED)
        client.screen.blit(mark, (rect.centerx - mark.get_width() // 2, rect.y + 4))
        name = _text(client, client.font_tiny, label[:6], INK)
        client.screen.blit(name, (rect.centerx - name.get_width() // 2, rect.y + 22))
        if key == "quests":
            active_q = _current_quest(client)
            if active_q:
                pygame.draw.circle(client.screen, GOLD, (rect.right - 8, rect.y + 8), 4)
        rects[key] = rect
    client.hud_world_rects["nav"] = rects


def _draw_action_bar(client):
    MAP_W, MAP_H, _sx, _sw, _sh = _layout()
    labels = ("1", "2", "3", "4", "5", "Eat")
    keys = ("attack", "strength", "defence", "hitpoints", "archery", "eat")
    width = 46 * len(labels) + 8
    origin = pygame.Rect(MAP_W // 2 - width // 2, MAP_H - 52, width, 44)
    _panel(client.screen, origin, (10, 14, 28), GOLD_DIM, radius=10)
    rects = {}
    for i, (key, label) in enumerate(zip(keys, labels)):
        rect = pygame.Rect(origin.x + 6 + i * 46, origin.y + 6, 40, 32)
        _panel(client.screen, rect, NAVY_HI, GOLD_DIM, radius=6)
        surf = _text(client, client.font_tiny, label, GOLD if key != "eat" else SAFE_GREEN)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
        rects[key] = rect
    client.hud_world_rects["actions"] = rects


def _draw_event_banner(client):
    event = getattr(client, "world_event", None)
    if not event:
        client.hud_world_rects["event"] = None
        return
    MAP_W, _mh, _sx, _sw, _sh = _layout()
    name = str(event.get("name") or "World Event")
    place = str(event.get("location") or "")
    title = _text(client, client.font_small, name, GOLD)
    rect = pygame.Rect(MAP_W // 2 - 160, 8, 320, 36)
    _panel(client.screen, rect, NAVY, GOLD, radius=8, width=2)
    client.screen.blit(title, (rect.x + 10, rect.y + 4))
    _blit(client, client.font_tiny, place, (rect.x + 10, rect.y + 20), MUTED)
    join = pygame.Rect(rect.right - 62, rect.y + 6, 52, 24)
    _panel(client.screen, join, (40, 70, 48), SAFE_GREEN, radius=6)
    lab = _text(client, client.font_tiny, "Join", INK)
    client.screen.blit(lab, (join.centerx - lab.get_width() // 2, join.centery - lab.get_height() // 2))
    client.hud_world_rects["event"] = {"box": rect, "join": join, "event": event}


def draw_sidebar(client):
    ensure(client)
    _mw, _mh, SIDEBAR_X, SCREEN_W, SCREEN_H = _layout()
    client.logout_btn_rect = None
    client.sidebar_settings_rect = None
    client.sidebar_bank_btn_rect = None
    client.skills_btn_rect = None
    client.pets_btn_rect = None
    client.auto_pickup_btn_rect = None
    client.sidebar_action_rects = {}
    client.sidebar_tab_rects = {}
    rects = {}
    panel = pygame.Rect(SIDEBAR_X, 0, SCREEN_W - SIDEBAR_X, SCREEN_H)
    pygame.draw.rect(client.screen, NAVY, panel)
    pygame.draw.line(client.screen, GOLD, (SIDEBAR_X, 0), (SIDEBAR_X, SCREEN_H), 2)
    y = 8
    y = _draw_header(client, y, rects)
    y = _draw_currencies(client, y, rects)
    y = _draw_quest_card(client, y, rects)
    y = _draw_system_tabs(client, y, rects)
    bottom = SCREEN_H - 80
    _draw_system_body(client, y, bottom, rects)
    _draw_skills_button(client, rects)
    _draw_utility_row(client, rects)
    if client.hud_menu:
        _draw_menu(client, rects)
    client.hud_rects = rects


def _draw_header(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 10
    w = SCREEN_W - SIDEBAR_X - 20
    card = pygame.Rect(x0, y, w, 78)
    _panel(client.screen, card, NAVY_CARD, GOLD_DIM)
    pygame.draw.circle(client.screen, NAVY_HI, (card.x + 28, card.y + 28), 18)
    pygame.draw.circle(client.screen, GOLD, (card.x + 28, card.y + 28), 18, 2)
    name = (client.player or {}).get("name") or "Adventurer"
    level = client.player_combat_level()
    _blit(client, client.font, name[:14], (card.x + 54, card.y + 6), INK)
    frac, _lvl = _xp_fraction(client)
    level_line = _text(client, client.font_tiny, f"Lv {level}  {int(frac * 100)}%", GOLD)
    client.screen.blit(level_line, (card.x + 54, card.y + 26))
    settings_x = SCREEN_W - 102
    bar_x = card.x + 62 + level_line.get_width()
    bar_w = settings_x - 8 - bar_x
    if bar_w > 16:
        bar = pygame.Rect(bar_x, card.y + 28, bar_w, 8)
        pygame.draw.rect(client.screen, (8, 10, 18), bar, border_radius=4)
        fill = bar.copy()
        fill.w = max(0, int(bar.w * frac))
        pygame.draw.rect(client.screen, GOLD, fill, border_radius=4)
    ribbon = pygame.Rect(card.x + 54, card.y + 46, card.w - 68, 22)
    _panel(client.screen, ribbon, (36, 28, 48), GOLD, radius=6)
    _blit(client, client.font_tiny, _title(client)[:18], (ribbon.x + 8, ribbon.y + 3), GOLD)
    settings = pygame.Rect(SCREEN_W - 102, 8, 92, 26)
    _panel(client.screen, settings, NAVY_HI, GOLD, radius=6, width=2)
    _gear_mark(client.screen, settings.x + 14, settings.centery)
    label = _text(client, client.font_tiny, "Settings", GOLD)
    client.screen.blit(label, (settings.x + 26, settings.centery - label.get_height() // 2))
    rects["settings"] = settings
    client.sidebar_settings_rect = settings
    return card.bottom + 6


def _gear_mark(screen, cx, cy):
    """Small gear, the old settings mark."""
    pygame.draw.circle(screen, GOLD, (cx, cy), 6, 2)
    pygame.draw.circle(screen, GOLD, (cx, cy), 2)
    for dx, dy in ((0, -8), (6, -6), (8, 0), (6, 6), (0, 8), (-6, 6), (-8, 0), (-6, -6)):
        pygame.draw.line(screen, GOLD, (cx + dx // 2, cy + dy // 2), (cx + dx, cy + dy), 2)


def _draw_currencies(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 10
    w = SCREEN_W - SIDEBAR_X - 20
    row = pygame.Rect(x0, y, w, 28)
    _panel(client.screen, row, NAVY_CARD, GOLD_DIM, radius=6)
    coins = int((client.player or {}).get("coins") or 0)
    _blit(client, client.font_tiny, "No guild", (row.x + 8, row.y + 6), MUTED)
    _blit(client, client.font_tiny, f"{coins:,} gold", (row.x + 90, row.y + 6), GOLD)
    _blit(client, client.font_tiny, f"{_gem_count(client)} gems", (row.x + 190, row.y + 6), (140, 190, 255))
    return row.bottom + 6


def _draw_quest_card(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 10
    w = SCREEN_W - SIDEBAR_X - 20
    card = pygame.Rect(x0, y, w, 52)
    _panel(client.screen, card, NAVY_CARD, GOLD_DIM)
    _blit(client, client.font_tiny, "Current Quest", (card.x + 8, card.y + 4), GOLD)
    quest = _current_quest(client)
    if not quest:
        _blit(client, client.font_tiny, "No active quest", (card.x + 8, card.y + 24), MUTED)
    else:
        name, _desc, progress, need, status = quest
        _blit(client, client.font_small, name[:28], (card.x + 8, card.y + 18), INK)
        detail = status.replace("_", " ")
        if need:
            detail = f"{progress}/{need}"
        _blit(client, client.font_tiny, detail, (card.x + 8, card.y + 34), MUTED)
    rects["quest_card"] = card
    return card.bottom + 6


def _draw_system_tabs(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 10
    w = SCREEN_W - SIDEBAR_X - 20
    tab_w = w // 4
    boxes = {}
    for i, (key, label) in enumerate(SYSTEMS):
        rect = pygame.Rect(x0 + i * tab_w, y, tab_w - 4, 32)
        active = client.hud_system == key and not client.hud_focus
        _panel(client.screen, rect, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM, radius=6, width=2 if active else 1)
        surf = _text(client, client.font_tiny, label, INK if active else MUTED)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
        boxes[key] = rect
    rects["systems"] = boxes
    return y + 38


def _draw_system_body(client, y, bottom, rects):
    focus = client.hud_focus
    if focus == "lore":
        _draw_lore(client, y, bottom)
        return
    if focus == "achievements":
        _draw_achievements(client, y, bottom)
        return
    if focus in ("mounts", "party", "guild", "events"):
        messages = {
            "mounts": "No mounts yet.",
            "party": "You are not in a party.",
            "guild": "You are not in a guild.",
            "events": "No world event is active.",
        }
        _blit(client, client.font_small, messages[focus], ( _body_x() + 8, y + 8), MUTED)
        return
    system = client.hud_system
    if system == "inventory":
        _draw_inventory(client, y, bottom, rects)
    elif system == "crafting":
        _draw_crafting(client, y, bottom, rects)
    elif system == "gathering":
        _draw_gathering(client, y, bottom, rects)
    else:
        _draw_bags(client, y, bottom, rects)


def _body_x():
    _mw, _mh, sidebar_x, _sw, _sh = _layout()
    return sidebar_x + 10


def _body_w():
    _mw, _mh, sidebar_x, screen_w, _sh = _layout()
    return screen_w - sidebar_x - 20


def _panel_blocking_hover(client):
    names = (
        "show_bank", "show_forge", "show_cook", "show_equipment", "show_help",
        "show_shop_panel", "show_skills", "show_pets", "show_travel",
        "drop_prompt", "dialogue",
    )
    return any(getattr(client, name, None) for name in names)


def _draw_inventory(client, y, bottom, rects):
    x0 = _body_x()
    filled = len(_inventory_entries(client))
    _blit(client, client.font_tiny, f"{filled} / {INVENTORY_SIZE}", (x0, y), MUTED)
    y += 16
    filters = {}
    short = {"all": "All", "weapons": "Wpn", "armour": "Arm", "consumables": "Food", "materials": "Mat", "quest": "Quest"}
    chip_w = (_body_w() - 8) // 3
    for i, (key, _label) in enumerate(FILTERS):
        col, row = i % 3, i // 3
        rect = pygame.Rect(x0 + col * (chip_w + 4), y + row * 20, chip_w, 18)
        active = client.hud_filter == key
        _panel(client.screen, rect, NAVY_HI if active else NAVY, GOLD if active else GOLD_DIM, radius=4)
        surf = _text(client, client.font_tiny, short[key], INK if active else MUTED)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.y + 1))
        filters[key] = rect
    rects["filters"] = filters
    y += 42
    rows = _filtered_entries(client)
    cols = 4
    gap = 4
    size = max(40, min(48, (_body_w() - gap * (cols - 1)) // cols))
    row_h = size + gap
    slots = {}
    hover = None
    import procedural_sprites_finished as sprites
    slot_bottom = bottom - 40
    visible_rows = max(1, (slot_bottom - y) // row_h)
    total_rows = (len(rows) + cols - 1) // cols if rows else 0
    max_scroll = max(0, total_rows - visible_rows)
    scroll = max(0, min(max_scroll, int(getattr(client, "hud_inv_scroll", 0) or 0)))
    client.hud_inv_scroll = scroll
    client.hud_inv_max_scroll = max_scroll
    start = scroll * cols
    for i, (slot, entry) in enumerate(rows[start:start + visible_rows * cols]):
        col, row = i % cols, i // cols
        rect = pygame.Rect(x0 + col * (size + gap), y + row * row_h, size, size)
        if rect.bottom > slot_bottom:
            break
        selected = slot == client.hud_selected
        pygame.draw.rect(client.screen, NAVY_HI if entry else NAVY, rect, border_radius=6)
        pygame.draw.rect(client.screen, GOLD if selected else GOLD_DIM, rect, 2 if selected else 1, border_radius=6)
        sprites.draw_item_icon(client.screen, rect.inflate(-8, -8), entry["item_id"], ITEMS)
        if int(entry.get("qty") or 1) > 1:
            qty = _text(client, client.font_tiny, str(entry["qty"]), GOLD)
            client.screen.blit(qty, (rect.right - qty.get_width() - 4, rect.bottom - qty.get_height() - 2))
        slots[slot] = rect
        if rect.collidepoint(pygame.mouse.get_pos()) and not getattr(client, "inv_drag", None):
            hover = (entry, rect)
    rects["slots"] = slots
    rects["inv_scroll_up"] = None
    rects["inv_scroll_down"] = None
    if max_scroll:
        up = pygame.Rect(x0 + _body_w() - 36, y - 58, 16, 14)
        down = pygame.Rect(up.right + 2, up.y, 16, 14)
        for rect, label, enabled in (
            (up, "^", scroll > 0),
            (down, "v", scroll < max_scroll),
        ):
            _panel(client.screen, rect, NAVY_HI if enabled else NAVY, GOLD if enabled else GOLD_DIM, radius=3)
            surf = _text(client, client.font_tiny, label, INK if enabled else MUTED)
            client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.y))
        rects["inv_scroll_up"] = up
        rects["inv_scroll_down"] = down
    rects["actions"] = {}
    equip = pygame.Rect(x0, bottom - 32, _body_w(), 28)
    active = bool(getattr(client, "show_equipment", False))
    _panel(client.screen, equip, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM, radius=6, width=2)
    surf = _text(client, client.font_small, "Equipment", INK)
    client.screen.blit(surf, (equip.centerx - surf.get_width() // 2, equip.centery - surf.get_height() // 2))
    rects["equipment"] = equip
    if hover and not _panel_blocking_hover(client):
        pygame.draw.rect(client.screen, GOLD, hover[1], 2, border_radius=6)
        client.draw_inventory_tooltip(hover[0], hover[1])


def _station_state(client, kind):
    px, py = client.player_xy()
    if kind == "forge":
        if client.near_forge():
            return "Near"
        return f"{_dist(client, 80, 6)} away"
    if kind == "cook":
        for spot in client.interactables or []:
            if spot.get("kind") in ("range", "fireplace") and max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 1:
                return "Near"
        return f"{_dist(client, 5, 41)} away"
    if kind == "fletch":
        return "Near" if _has_knife(client) else "Need knife"
    return f"{_dist(client, 98, 22)} away"


def _dist(client, x, y):
    px, py = client.player_xy()
    return max(abs(int(px) - x), abs(int(py) - y))


def _has_knife(client):
    for _slot, entry in _inventory_entries(client):
        item = ITEMS.get(entry.get("item_id")) or {}
        if entry.get("item_id") == "knife" or item.get("tool_for") == "fletching":
            return True
    return False


def _draw_crafting(client, y, bottom, rects):
    stations = (
        ("forge", "Forge", "Smelt and smith"),
        ("fletch", "Fletching", "Bows and arrows"),
        ("cook", "Cooking", "Cook food"),
        ("alchemy", "Alchemy", "Combat potions"),
    )
    boxes = {}
    x0 = _body_x()
    for key, title, blurb in stations:
        if y + 48 > bottom:
            break
        rect = pygame.Rect(x0, y, _body_w(), 44)
        state = _station_state(client, key)
        border = SAFE_GREEN if state == "Near" else GOLD_DIM
        _panel(client.screen, rect, NAVY_CARD, border)
        _blit(client, client.font_small, title, (rect.x + 8, rect.y + 4), INK)
        _blit(client, client.font_tiny, blurb, (rect.x + 8, rect.y + 24), MUTED)
        tag = _text(client, client.font_tiny, state, SAFE_GREEN if state == "Near" else GOLD)
        client.screen.blit(tag, (rect.right - tag.get_width() - 8, rect.y + 12))
        boxes[key] = rect
        y += 48
    rects["stations"] = boxes


def _skill_bar(client, skill, x, y, width):
    levels = (client.player or {}).get("levels") or {}
    xp_map = (client.player or {}).get("xp") or {}
    level = int(levels.get(skill) or 1)
    total = int(xp_map.get(skill) or 0)
    cur = combat.xp_for_level(combat.level_from_xp(total) if total else level)
    nxt = combat.xp_for_level((combat.level_from_xp(total) if total else level) + 1)
    frac = 0 if nxt <= cur else max(0.0, min(1.0, (total - cur) / (nxt - cur)))
    name = SKILL_DISPLAY_NAMES.get(skill, skill.title())
    _blit(client, client.font_small, f"{name}  {level}", (x, y), INK)
    bar = pygame.Rect(x, y + 18, width, 8)
    pygame.draw.rect(client.screen, (8, 10, 18), bar, border_radius=4)
    fill = bar.copy()
    fill.w = int(bar.w * frac)
    pygame.draw.rect(client.screen, GOLD, fill, border_radius=4)
    return 32


def _draw_gathering(client, y, bottom, rects):
    x0 = _body_x()
    w = _body_w() - 8
    for skill in ("mining", "woodcutting", "fishing"):
        if y + 36 > bottom:
            break
        y += _skill_bar(client, skill, x0, y, w)
        y += 6
    gather = (client.player or {}).get("gathering") or {}
    if isinstance(gather, dict) and gather.get("skill"):
        _blit(client, client.font_tiny, f"Gathering {gather.get('skill')}", (x0, y), SAFE_GREEN)
        y += 18
    nearest = _nearest_node(client)
    if nearest:
        kind, dist = nearest
        _blit(client, client.font_tiny, f"Nearest {kind}  ·  {dist} tiles", (x0, y), MUTED)
    walk = {}
    for i, (key, label) in enumerate((("mining", "Mine"), ("woodcutting", "Chop"), ("fishing", "Fish"))):
        rect = pygame.Rect(x0 + i * 90, bottom - 30, 84, 26)
        _panel(client.screen, rect, NAVY_HI, GOLD_DIM, radius=6)
        surf = _text(client, client.font_tiny, label, INK)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
        walk[key] = rect
    rects["gather"] = walk


def _nearest_node(client):
    resources = getattr(client, "resources", None) or {}
    px, py = client.player_xy()
    best = None
    for key, kind in resources.items():
        if not kind:
            continue
        try:
            x, y = key.split(",")
            x, y = int(x), int(y)
        except ValueError:
            continue
        dist = max(abs(x - int(px)), abs(y - int(py)))
        if best is None or dist < best[1]:
            best = (str(kind).replace("_", " "), dist)
    return best


def _draw_bags(client, y, bottom, rects):
    x0 = _body_x()
    _blit(client, client.font_tiny, "Bulk storage  ·  not worn gear", (x0, y), MUTED)
    y += 18
    boxes = {}
    player = client.player or {}
    for label, flag, total_key, cap in BAG_ROWS:
        if y + 28 > bottom:
            break
        owned = bool(player.get(flag))
        total = int(player.get(total_key) or 0)
        rect = pygame.Rect(x0, y, _body_w(), 26)
        _panel(client.screen, rect, NAVY_CARD, GOLD if owned else GOLD_DIM, radius=5)
        _blit(client, client.font_tiny, label, (rect.x + 8, rect.y + 5), INK if owned else MUTED)
        detail = f"{total} / {cap}" if owned else "Not owned"
        surf = _text(client, client.font_tiny, detail, GOLD if owned else MUTED)
        client.screen.blit(surf, (rect.right - surf.get_width() - 8, rect.y + 5))
        boxes[label] = rect
        y += 28
    rects["bags"] = boxes


def _draw_lore(client, y, bottom):
    x0 = _body_x()
    _blit(client, client.font_small, "Lore", (x0, y), GOLD)
    y += 22
    shown = 0
    for qid, state in (client.quests or {}).items():
        if y > bottom - 36 or shown >= 4:
            break
        status = (state or {}).get("status")
        if status in (None, "not_started"):
            continue
        spec = QUESTS.get(qid) or {}
        _blit(client, client.font_tiny, spec.get("name") or qid, (x0, y), INK)
        desc = (spec.get("description") or "")[:70]
        _blit(client, client.font_tiny, desc, (x0, y + 14), MUTED)
        y += 36
        shown += 1
    if shown == 0:
        _blit(client, client.font_tiny, "Quest stories appear here as you take them.", (x0, y), MUTED)


def _draw_achievements(client, y, bottom):
    points = 0
    done = 0
    for qid, state in (client.quests or {}).items():
        if (state or {}).get("status") == "complete":
            done += 1
            points += int((QUESTS.get(qid) or {}).get("quest_points") or 0)
    x0 = _body_x()
    _blit(client, client.font_small, "Achievements", (x0, y), GOLD)
    _blit(client, client.font_tiny, f"{done} quests complete", (x0, y + 24), INK)
    _blit(client, client.font_tiny, f"{points} quest points", (x0, y + 42), MUTED)


def _draw_skills_button(client, rects):
    """Opens the same skills modal the old sidebar used."""
    _mw, _mh, sidebar_x, screen_w, screen_h = _layout()
    rect = pygame.Rect(sidebar_x + 8, screen_h - 74, screen_w - sidebar_x - 16, 30)
    active = bool(getattr(client, "show_skills", False))
    _panel(client.screen, rect, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM, radius=6, width=2 if active else 1)
    combat = client.player_combat_level()
    total = client.player_total_level()
    label = _text(client, client.font_small, f"Skills   Combat {combat}   Total {total}", INK)
    client.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))
    rects["skills"] = rect
    client.skills_btn_rect = rect


def _draw_utility_row(client, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, SCREEN_H = _layout()
    keys = (("mounts", "Mounts"), ("pets", "Pets"), ("lore", "Lore"), ("achievements", "Achieve"), ("menu", "Menu"))
    x0 = SIDEBAR_X + 8
    w = (SCREEN_W - SIDEBAR_X - 16) // len(keys)
    y = SCREEN_H - 38
    boxes = {}
    for i, (key, label) in enumerate(keys):
        rect = pygame.Rect(x0 + i * w, y, w - 4, 30)
        active = client.hud_focus == key or (key == "menu" and client.hud_menu)
        _panel(client.screen, rect, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM, radius=6)
        surf = _text(client, client.font_tiny, label[:6], INK)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
        boxes[key] = rect
    rects["utility"] = boxes


def _draw_menu(client, rects):
    menu_btn = (rects.get("utility") or {}).get("menu")
    if not menu_btn:
        return
    box = pygame.Rect(menu_btn.x - 40, menu_btn.y - 70, 110, 64)
    _panel(client.screen, box, NAVY, GOLD, radius=8, width=2)
    help_r = pygame.Rect(box.x + 6, box.y + 6, box.w - 12, 24)
    logout_r = pygame.Rect(box.x + 6, box.y + 34, box.w - 12, 24)
    _panel(client.screen, help_r, NAVY_HI, GOLD_DIM, radius=4)
    _panel(client.screen, logout_r, (70, 32, 32), DANGER_RED, radius=4)
    _blit(client, client.font_tiny, "Help", (help_r.x + 8, help_r.y + 4), INK)
    _blit(client, client.font_tiny, "Logout", (logout_r.x + 8, logout_r.y + 4), INK)
    rects["menu_help"] = help_r
    rects["menu_logout"] = logout_r


def draw_chat(client):
    ensure(client)
    MAP_W, MAP_H, _sx, _sw, SCREEN_H = _layout()
    box = pygame.Rect(0, MAP_H, MAP_W, SCREEN_H - MAP_H)
    pygame.draw.rect(client.screen, NAVY, box)
    pygame.draw.line(client.screen, GOLD, (0, MAP_H), (MAP_W, MAP_H), 2)
    tabs = {}
    x = 8
    for channel in CHANNELS:
        label = channel.title()
        surf = _text(client, client.font_tiny, label, INK if client.hud_channel == channel else MUTED)
        rect = pygame.Rect(x, MAP_H + 4, surf.get_width() + 14, 18)
        if client.hud_channel == channel:
            _panel(client.screen, rect, NAVY_HI, GOLD, radius=4)
        client.screen.blit(surf, (rect.x + 7, rect.y + 1))
        tabs[channel] = rect
        x = rect.right + 4
    client.hud_rects["channels"] = tabs
    quick_x = MAP_W - 108
    log_right = quick_x - 8
    lines = _visible_lines(client)
    y = MAP_H + 26
    for line in lines[-6:]:
        color = line.get("color") or CHANNEL_COLOR.get(line.get("channel") or "system", INK)
        surf = _text(client, client.font_tiny, str(line.get("text") or "")[:78], color)
        client.screen.blit(surf, (10, y))
        y += 16
    quick = {}
    qy = MAP_H + 26
    for phrase in QUICK:
        rect = pygame.Rect(quick_x, qy, 100, 18)
        _panel(client.screen, rect, NAVY_CARD, GOLD_DIM, radius=4)
        surf = _text(client, client.font_tiny, phrase, INK)
        client.screen.blit(surf, (rect.x + 6, rect.y + 1))
        quick[phrase] = rect
        qy += 20
    client.hud_rects["quick"] = quick
    input_rect = pygame.Rect(8, SCREEN_H - 26, log_right - 8, 20)
    _panel(client.screen, input_rect, (8, 12, 24), GOLD if client.chat_typing else GOLD_DIM, radius=4)
    prompt = ("> " + client.chat_text) if client.chat_typing else "Press Enter to chat"
    _blit(client, client.font_tiny, prompt[:70], (input_rect.x + 6, input_rect.y + 2), INK if client.chat_typing else MUTED)
    client.hud_rects["chat_input"] = input_rect


def _line_dict(line):
    if isinstance(line, dict):
        return line
    return {"text": str(line), "color": INK, "channel": "system"}


def _visible_lines(client):
    channel = client.hud_channel
    rows = []
    for raw in client.chat_log:
        line = _line_dict(raw)
        tagged = line.get("channel")
        if channel == "all" or tagged == channel or (tagged is None and channel == "world"):
            rows.append(line)
    return rows


def handle_world_chrome_click(client, mx, my, button):
    ensure(client)
    world = client.hud_world_rects or {}
    event = world.get("event") or {}
    join = event.get("join")
    if join and join.collidepoint(mx, my):
        place = (event.get("event") or {}).get("location")
        client.add_chat("No world event to join." if not place else f"Head toward {place}.")
        return True
    for key, rect in (world.get("nav") or {}).items():
        if rect.collidepoint(mx, my):
            _nav_click(client, key)
            return True
    for key, rect in (world.get("actions") or {}).items():
        if rect.collidepoint(mx, my):
            _action_click(client, key)
            return True
    return False


def _nav_click(client, key):
    client.hud_menu = False
    if key == "map":
        client.toggle_world_map()
        return
    if key == "pvp":
        client.hud_pvp_mode = not client.hud_pvp_mode
        client.add_chat(
            "PvP marker on. Other players are not attackable."
            if client.hud_pvp_mode else
            "PvP marker off."
        )
        return
    if key == "quests":
        client.hud_focus = None
        client.hud_system = "inventory"
        client.add_chat("Quest progress is on the sidebar card.")
        return
    client.hud_focus = key
    client.hud_system = "inventory"


def _action_click(client, key):
    if key == "eat":
        client.net.send("QUICK_CONSUME", kind="food")
        return
    client.set_combat_style(key)
    client.add_chat(f"Combat style: {key}.")


def handle_sidebar_click(client, mx, my, button):
    ensure(client)
    rects = client.hud_rects or {}
    if client.hud_menu:
        if rects.get("menu_logout") and rects["menu_logout"].collidepoint(mx, my):
            client.hud_menu = False
            client.logout()
            return
        if rects.get("menu_help") and rects["menu_help"].collidepoint(mx, my):
            client.hud_menu = False
            client.show_help = True
            client.help_scroll = 0
            return
        client.hud_menu = False
    if rects.get("settings") and rects["settings"].collidepoint(mx, my):
        client.show_help = not client.show_help
        if client.show_help:
            client.help_scroll = 0
            client.show_equipment = False
        return
    if rects.get("equipment") and rects["equipment"].collidepoint(mx, my):
        client.show_equipment = not client.show_equipment
        if client.show_equipment:
            client.show_help = False
            client.show_forge = False
            client.show_cook = False
            client.show_skills = False
            client.show_travel = False
            client.show_pets = False
        return
    if rects.get("skills") and rects["skills"].collidepoint(mx, my):
        client.toggle_skills_modal()
        return
    for key, rect in (rects.get("systems") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_system = key
            client.hud_focus = None
            return
    for key, rect in (rects.get("filters") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_filter = key
            client.hud_selected = None
            client.hud_inv_scroll = 0
            return
    if rects.get("inv_scroll_up") and rects["inv_scroll_up"].collidepoint(mx, my):
        client.hud_inv_scroll = max(0, int(getattr(client, "hud_inv_scroll", 0) or 0) - 1)
        return
    if rects.get("inv_scroll_down") and rects["inv_scroll_down"].collidepoint(mx, my):
        cap = int(getattr(client, "hud_inv_max_scroll", 0) or 0)
        client.hud_inv_scroll = min(cap, int(getattr(client, "hud_inv_scroll", 0) or 0) + 1)
        return
    for slot, rect in (rects.get("slots") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_selected = slot
            _activate_slot(client, slot, button if button == 3 else 1)
            return
    for key, rect in (rects.get("actions") or {}).items():
        if rect.collidepoint(mx, my):
            _inventory_action(client, key)
            return
    for key, rect in (rects.get("stations") or {}).items():
        if rect.collidepoint(mx, my):
            _station_click(client, key)
            return
    for key, rect in (rects.get("gather") or {}).items():
        if rect.collidepoint(mx, my):
            _gather_click(client, key)
            return
    for key, rect in (rects.get("utility") or {}).items():
        if rect.collidepoint(mx, my):
            _utility_click(client, key)
            return
    for channel, rect in (rects.get("channels") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_channel = channel
            return
    for phrase, rect in (rects.get("quick") or {}).items():
        if rect.collidepoint(mx, my):
            client.net.send("CHAT", text=phrase)
            client.add_chat(f"You: {phrase}", color=CHANNEL_COLOR["world"])
            return
    chat_input = rects.get("chat_input")
    if chat_input and chat_input.collidepoint(mx, my):
        client.chat_typing = True
        return


def _inventory_action(client, key):
    slot, entry = _selected_entry(client)
    if slot is None or not entry:
        client.add_chat("Select an item first.")
        return
    if key in ("equip", "use"):
        _activate_slot(client, slot, 1)
        return
    if key == "drop":
        _activate_slot(client, slot, 3)
        return
    qty = int(entry.get("qty") or 1)
    if qty < 2:
        client.add_chat("Nothing to split.")
        return
    client.open_drop_prompt(slot, entry)


def _station_click(client, key):
    if key == "forge":
        if client.near_forge():
            client.open_forge_at()
        else:
            client.travel_to_destination({"label": "Smithy Furnace", "x": 80, "y": 7, "action": None})
        return
    if key == "fletch":
        if _has_knife(client):
            client.open_fletch()
        else:
            client.add_chat("Bring a knife to fletch.")
        return
    if key == "cook":
        if _station_state(client, "cook") == "Near":
            client.open_cook()
        else:
            client.travel_to_destination({"label": "Inn Hearth", "x": 5, "y": 41, "action": {"type": "COOK"}})
        return
    client.travel_to_destination({"label": "Mad Scientist", "x": 98, "y": 22, "action": None})


def _gather_click(client, key):
    client.hud_focus = None
    client.toggle_skills_modal()
    client.add_chat(f"Open skills for {SKILL_DISPLAY_NAMES.get(key, key)}. Click a node in the world to gather.")


def _utility_click(client, key):
    if key == "menu":
        client.hud_menu = not client.hud_menu
        return
    client.hud_menu = False
    if key == "pets":
        client.toggle_pets_modal()
        return
    if key == "lore":
        client.hud_focus = None if client.hud_focus == "lore" else "lore"
        return
    if key == "achievements":
        client.hud_focus = None if client.hud_focus == "achievements" else "achievements"
        return
    client.hud_focus = key
