"""Navy / gold HUD chrome. Drawn only when USE_NEW_HUD is on.

World rendering, networking, and inventory rules stay in client.py. This module
paints the sidebar, chat, left nav, zone chip, and action bar, and forwards
clicks to the existing equip / use / forge / cook handlers.
"""
import math
import os
import pygame

import combat
from content import (
    ITEMS, QUESTS, NPCS, SKILL_DISPLAY_NAMES, STORAGE_BAG_IDS, INVENTORY_SIZE,
    COOKED_FISH_IDS, TRAVEL_DESTINATIONS, is_gem_item, is_storage_bag, is_food,
)

NAVY = (12, 18, 34)
NAVY_CARD = (20, 28, 48)
NAVY_HI = (32, 42, 68)
NAVY_DEEP = (8, 12, 24)
GOLD = (212, 175, 90)
GOLD_BRIGHT = (242, 210, 120)
GOLD_DIM = (120, 96, 52)
INK = (232, 226, 210)
MUTED = (150, 160, 180)
SAFE_GREEN = (72, 180, 110)
DANGER_RED = (210, 70, 70)

_HUD_DIR = os.path.join(os.path.dirname(__file__), "assets", "hud")
_ART = {}  # path -> Surface
_PORTRAIT_CACHE = {}  # (key, size) -> Surface

SAFE_ZONES = {"village", "city", "fishing_village"}
ZONE_NAMES = {
    "fairy_village": "Fairy Glade",
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
CHANNELS = ("world", "guild", "party", "whisper")
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
    ("Fletching Pouch", "has_fletch_pouch", "fletch_pouch_total", 5000),
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
    client.hud_inv_scroll_drag = None
    client.hud_inv_scroll_meta = None
    client.hud_channel = "world"
    client.hud_pvp_mode = False
    client.hud_menu = False
    client.hud_focus = None
    client.hud_rects = {}
    client.hud_world_rects = {}
    client.guild_scroll = 0
    client.guild_selected = None
    client.guild_tab = "home"  # home | members | bank


def _hud_art(name):
    """Lazy-load a PNG from client/assets/hud (None if missing)."""
    if name in _ART:
        return _ART[name]
    path = os.path.join(_HUD_DIR, name)
    if not os.path.isfile(path):
        _ART[name] = None
        return None
    try:
        img = pygame.image.load(path)
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        _ART[name] = img
    except Exception:
        _ART[name] = None
    return _ART[name]


def reload_hud_art():
    """Drop cached HUD textures (call after replacing assets)."""
    _ART.clear()


def _panel(surf, rect, fill=NAVY_CARD, border=GOLD_DIM, radius=8, width=1, ornate=False):
    """Card with soft depth: shadow, gradient body, inner rim, gold edge, optional corners."""
    if rect.w < 4 or rect.h < 4:
        return
    # Drop shadow
    shadow = rect.move(2, 3)
    sh = pygame.Surface((shadow.w, shadow.h), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, 70), sh.get_rect(), border_radius=radius)
    surf.blit(sh, shadow.topleft)
    # Body
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    # Vertical gradient sheen (top lighter) — clipped by a rounded mask
    gh = max(2, rect.h // 2)
    gloss = pygame.Surface((rect.w, gh), pygame.SRCALPHA)
    for i in range(gh):
        a = int(22 * (1.0 - i / max(1, gh - 1)))
        pygame.draw.line(gloss, (210, 190, 140, a), (0, i), (rect.w, i))
    mask = pygame.Surface((rect.w, gh), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    gloss.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(gloss, rect.topleft)
    # Inner rim + top highlight
    inset = rect.inflate(-4, -4)
    if inset.w > 6 and inset.h > 6:
        pygame.draw.rect(surf, NAVY_HI, inset, 1, border_radius=max(2, radius - 2))
        hi = tuple(min(255, c + 48) for c in fill)
        pygame.draw.line(surf, hi, (inset.x + 5, inset.y + 1), (inset.right - 5, inset.y + 1), 1)
    # Outer gold border (brighter when ornate / primary)
    edge = GOLD_BRIGHT if ornate or border == GOLD else border
    pygame.draw.rect(surf, edge, rect, max(1, width), border_radius=radius)
    # Double rim only on large ornate cards — small popups keep a single clean edge
    # so rounded corners don't leave bright wedge artifacts.
    if ornate and rect.w >= 100 and rect.h >= 48:
        outer = rect.inflate(2, 2)
        pygame.draw.rect(surf, GOLD_DIM, outer, 1, border_radius=radius + 1)
        _draw_corner_flourishes(surf, rect)


def _draw_corner_flourishes(surf, rect):
    """Muted gold L-brackets. Drawn (not AI art) so corners never wash out white."""
    arm = max(8, min(14, rect.w // 14, rect.h // 5))
    for cx, cy, dx, dy in (
        (rect.x + 6, rect.y + 6, 1, 1),
        (rect.right - 7, rect.y + 6, -1, 1),
        (rect.x + 6, rect.bottom - 7, 1, -1),
        (rect.right - 7, rect.bottom - 7, -1, -1),
    ):
        pygame.draw.line(surf, GOLD_DIM, (cx, cy), (cx + dx * arm, cy), 2)
        pygame.draw.line(surf, GOLD_DIM, (cx, cy), (cx, cy + dy * arm), 2)
        pygame.draw.line(surf, GOLD, (cx, cy), (cx + dx * (arm - 2), cy), 1)
        pygame.draw.line(surf, GOLD, (cx, cy), (cx, cy + dy * (arm - 2)), 1)
        pygame.draw.circle(surf, GOLD, (cx, cy), 2)


def _fill_bar(surf, rect, pct, color, radius=4):
    """Ornate meter: deep trough, fill, top gloss."""
    pygame.draw.rect(surf, NAVY_DEEP, rect, border_radius=radius)
    pygame.draw.rect(surf, GOLD_DIM, rect, 1, border_radius=radius)
    fill = rect.inflate(-2, -2)
    fill.w = max(0, int(fill.w * max(0.0, min(1.0, pct))))
    if fill.w > 0:
        pygame.draw.rect(surf, color, fill, border_radius=max(2, radius - 1))
        gloss = pygame.Surface((fill.w, max(1, fill.h // 2)), pygame.SRCALPHA)
        gloss.fill((255, 255, 255, 55))
        surf.blit(gloss, fill.topleft)


def _text(client, font, text, color):
    return font.render(str(text), True, color)


def _blit(client, font, text, xy, color=INK):
    surf = _text(client, font, text, color)
    client.screen.blit(surf, xy)
    return surf


def _fit_text(font, text, max_w):
    """Single-line ellipsis so the sidebar never overflows."""
    text = str(text or "")
    if font.size(text)[0] <= max_w:
        return text
    while len(text) > 1 and font.size(text + "…")[0] > max_w:
        text = text[:-1]
    return (text + "…") if text else ""


def _wrap_text(font, text, max_w, max_lines=2):
    """Word-wrap into up to max_lines; last line ellipsizes if truncated."""
    words = str(text or "").split()
    if not words:
        return []
    lines, cur = [], ""
    i = 0
    while i < len(words) and len(lines) < max_lines:
        word = words[i]
        trial = f"{cur} {word}".strip()
        if font.size(trial)[0] <= max_w:
            cur = trial
            i += 1
            continue
        if cur:
            lines.append(cur)
            cur = ""
            continue
        # Single word wider than the column — hard-fit it.
        lines.append(_fit_text(font, word, max_w))
        i += 1
        cur = ""
    if cur and len(lines) < max_lines:
        lines.append(cur)
        i = len(words)
    if i < len(words) and lines:
        lines[-1] = _fit_text(font, lines[-1].rstrip("…") + "…", max_w)
    return lines


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
    style = getattr(client, "combat_style", None) or "attack"
    if style not in ("attack", "strength", "defence", "archery"):
        style = "attack"
    total = int(xp_map.get(style) or 0)
    level = combat.level_from_xp(total)
    cur = combat.xp_for_level(level)
    nxt = combat.xp_for_level(level + 1)
    span = max(1, nxt - cur)
    return max(0.0, min(1.0, (total - cur) / span)), level


def _title(client):
    """Deed ribbon under the portrait: guild first, else best completed quest."""
    guild = str((_clan(client).get("name") or "")).strip()
    if guild:
        return guild
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


def _gold_divider(screen, x, y, w):
    """Ornate horizontal rule between sidebar sections."""
    art = _hud_art("gold_divider.png")
    if art is not None and w > 8:
        scaled = pygame.transform.smoothscale(art, (w, max(3, min(8, art.get_height()))))
        screen.blit(scaled, (x, y))
        return y + scaled.get_height() + 4
    pygame.draw.line(screen, GOLD_DIM, (x, y + 2), (x + w, y + 2), 1)
    pygame.draw.line(screen, GOLD_BRIGHT, (x + w // 4, y + 2), (x + 3 * w // 4, y + 2), 1)
    return y + 8


def all_other_quests_complete(client):
    """True once every quest except the Royal Challenge is finished.

    The Royal Challenge is an endgame checklist — guidance must not point at
    Elowen until the rest of the journal is done.
    """
    quests = client.quests or {}
    others = [qid for qid in QUESTS if qid != "fairy_oath"]
    if not others:
        return True
    return all((quests.get(qid) or {}).get("status") == "complete" for qid in others)


def _guideable_active(client):
    """Active/ready quests the NEXT ACTION card and trail may follow."""
    quests = client.quests or {}
    active = [
        qid for qid, state in quests.items()
        if state and (state.get("status") or "not_started") not in ("complete", "not_started")
    ]
    if "fairy_oath" in active and not all_other_quests_complete(client):
        active = [qid for qid in active if qid != "fairy_oath"]
    return active


def _tracked_quest_id(client):
    """Which quest the HUD tracks.

    The player's explicit choice (client.tracked_quest_id) wins whenever it is
    still an active quest, so the card never jumps just because another quest
    changed state. Without a choice, fall back deterministically: a quest that
    is ready to turn in beats one merely in progress, then dictionary order.

    The Royal Challenge is excluded until every other quest is complete.
    """
    quests = client.quests or {}
    active = _guideable_active(client)
    tracked = getattr(client, "tracked_quest_id", None)
    if tracked in active:
        return tracked
    ready = [qid for qid in active if (quests.get(qid) or {}).get("status") == "ready"]
    return (ready or active or [None])[0]


def _current_quest(client):
    qid = _tracked_quest_id(client)
    if not qid:
        return None
    state = (client.quests or {}).get(qid) or {}
    spec = QUESTS.get(qid) or {}
    progress = int(state.get("progress") or 0)
    need = int(spec.get("count") or 0)
    return spec.get("name") or qid, spec.get("description") or "", progress, need, state.get("status") or "not_started"


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
    for i, (key, label) in enumerate(zip(keys, labels)):
        rect = pygame.Rect(8, top + i * 46, 52, 42)
        pk_on = bool((getattr(client, "player", None) or {}).get("player_killer"))
        focus_on = client.hud_focus == key
        active = (key == "pvp" and pk_on) or (key != "pvp" and focus_on)
        border = DANGER_RED if (key == "pvp" and pk_on) else (GOLD_BRIGHT if active else GOLD)
        fill = NAVY_HI if active else NAVY
        _panel(client.screen, rect, fill, border, radius=8, width=2 if active else 1, ornate=active)
        mark = _text(client, client.font_tiny, label[:1],
                     DANGER_RED if (key == "pvp" and pk_on) else (GOLD_BRIGHT if active else GOLD))
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
    labels = ("1", "2", "3", "5", "Eat")
    keys = ("attack", "strength", "defence", "archery", "eat")
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


def _draw_sidebar_backdrop(screen, panel):
    """Leather-textured navy column with a gold binding rail."""
    leather = _hud_art("sidebar_leather.png")
    if leather is not None:
        # Tile leather, then multiply with navy so it stays Crownfall-dark.
        tile = leather
        for y in range(panel.y, panel.bottom, tile.get_height()):
            for x in range(panel.x, panel.right, tile.get_width()):
                screen.blit(tile, (x, y))
        wash = pygame.Surface(panel.size, pygame.SRCALPHA)
        # Lighter wash so the quilted leather grain stays visible.
        wash.fill((*NAVY, 110))
        screen.blit(wash, panel.topleft)
    else:
        pygame.draw.rect(screen, NAVY, panel)
    # Soft vignette at top/bottom
    vig = pygame.Surface((panel.w, 48), pygame.SRCALPHA)
    for i in range(48):
        a = int(90 * (1 - i / 47))
        pygame.draw.line(vig, (0, 0, 0, a), (0, i), (panel.w, i))
    screen.blit(vig, panel.topleft)
    screen.blit(pygame.transform.flip(vig, False, True), (panel.x, panel.bottom - 48))
    # Gold binding rail (book-spine feel)
    rail = pygame.Rect(panel.x, panel.y, 6, panel.h)
    pygame.draw.rect(screen, GOLD_DIM, rail)
    pygame.draw.rect(screen, GOLD, (panel.x + 1, panel.y, 3, panel.h))
    pygame.draw.line(screen, GOLD_BRIGHT, (panel.x + 2, panel.y), (panel.x + 2, panel.bottom), 1)
    for yy in range(panel.y + 18, panel.bottom - 10, 56):
        pygame.draw.circle(screen, GOLD_BRIGHT, (panel.x + 3, yy), 2)
        pygame.draw.circle(screen, (80, 60, 30), (panel.x + 3, yy), 2, 1)


def _portrait_cache_key(client):
    p = client.player or {}
    look = p.get("appearance") or {}
    if not isinstance(look, dict):
        look = {}
    eq = p.get("equipment") or {}
    return (
        p.get("gender") or "male",
        look.get("skin_tone"),
        look.get("hair"),
        look.get("hair_colour"),
        look.get("outfit") or look.get("top"),
        look.get("head"),
        eq.get("helmet") or eq.get("head"),
        eq.get("weapon"),
        bool(p.get("hd_player", True)),
    )


def _player_portrait(client, size=56):
    """Circular bust of the player's current look (cached)."""
    key = (_portrait_cache_key(client), size)
    cached = _PORTRAIT_CACHE.get(key)
    if cached is not None:
        return cached
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    # Warm medallion backdrop (readable if the sprite is sparse)
    pygame.draw.circle(out, (28, 36, 58), (size // 2, size // 2), size // 2)
    pygame.draw.circle(out, (48, 38, 28), (size // 2, size // 2), size // 2 - 2)
    drew = False
    try:
        import player_hd_client
        p = client.player or {}
        sex = "female" if (p.get("gender") or "male") == "female" else "male"
        look = p.get("appearance") or {}
        if not isinstance(look, dict) or not look:
            look = player_hd_client.get_default_appearance(sex, starter=True)
        # Large canvas + big tile so the head has enough pixels after crop.
        pad = 220
        canvas = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        player_hd_client.draw_player(
            canvas, sex, look, pad, pad + 90, 180, 0.0,
            anim="idle", facing="s", equipment=p.get("equipment"),
            fx_ctx={"preview": True},
        )
        box = canvas.get_bounding_rect()
        if box.w >= 4 and box.h >= 4:
            # Face + collar only. HD sprites are full-body; the head is the
            # top ~22% of the figure bounds (shoulders start ~25–30%).
            head_h = max(12, int(box.h * 0.24))
            inset = max(0, int(box.w * 0.10))
            head = pygame.Rect(
                box.x + inset, box.y,
                max(8, box.w - inset * 2), head_h,
            )
            head = head.clip(canvas.get_rect())
            bust = canvas.subsurface(head).copy()
            # Cover the inner medallion; prefer height so the face fills the ring.
            scale = max(
                (size * 1.05) / max(1, bust.get_width()),
                (size * 1.05) / max(1, bust.get_height()),
            )
            nw = max(1, int(bust.get_width() * scale))
            nh = max(1, int(bust.get_height() * scale))
            bust = pygame.transform.smoothscale(bust, (nw, nh))
            out.blit(bust, (size // 2 - nw // 2, size // 2 - nh // 2))
            drew = True
    except Exception:
        drew = False
    if not drew:
        letter = ((client.player or {}).get("name") or "A")[:1].upper()
        try:
            font = client.font
            surf = font.render(letter, True, INK)
            out.blit(surf, (size // 2 - surf.get_width() // 2,
                            size // 2 - surf.get_height() // 2))
        except Exception:
            pass
    # Circular clip
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2 - 1)
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    # Slim rim at HUD size so the face stays large; full filigree ring for big previews.
    ring_name = "portrait_ring.png" if size >= 96 else "portrait_rim_thin.png"
    ring = _hud_art(ring_name) or _hud_art("portrait_rim_thin.png")
    if ring is not None:
        out.blit(pygame.transform.smoothscale(ring, (size, size)), (0, 0))
    else:
        pygame.draw.circle(out, GOLD_DIM, (size // 2, size // 2), size // 2 - 1, 3)
        pygame.draw.circle(out, GOLD_BRIGHT, (size // 2, size // 2), size // 2 - 2, 1)
        pygame.draw.circle(out, (80, 60, 28), (size // 2, size // 2), size // 2 - 4, 1)
        for ang in (0, 90, 180, 270):
            rad = math.radians(ang)
            cx = size // 2 + int(math.cos(rad) * (size // 2 - 2))
            cy = size // 2 + int(math.sin(rad) * (size // 2 - 2))
            pygame.draw.circle(out, GOLD_BRIGHT, (cx, cy), 2)
    if len(_PORTRAIT_CACHE) > 24:
        _PORTRAIT_CACHE.clear()
    _PORTRAIT_CACHE[key] = out
    return out


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
    _draw_sidebar_backdrop(client.screen, panel)
    y = 8
    y = _draw_header(client, y, rects)
    _mw, _mh, sx, sw, _sh = _layout()
    y = _gold_divider(client.screen, sx + 18, y, sw - sx - 34)
    y = _draw_hitpoints(client, y)
    y = _draw_currencies(client, y, rects)
    y = _draw_quest_card(client, y, rects)
    y = _gold_divider(client.screen, sx + 18, y, sw - sx - 34)
    y = _draw_system_tabs(client, y, rects)
    # Utility (Mounts/Pets/…) lives under the combat styles on the chat strip,
    # so the sidebar only keeps Skills at the bottom and gives the bag more height.
    bottom = SCREEN_H - 42
    _draw_system_body(client, y, bottom, rects)
    _draw_skills_button(client, rects)
    # Keep any utility rects drawn earlier this frame (combat bar) so Menu /
    # Guild click handlers still find them after we rebuild hud_rects.
    prior_utility = (getattr(client, "hud_rects", None) or {}).get("utility")
    client.hud_rects = rects
    if prior_utility:
        rects["utility"] = prior_utility


def _draw_header(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 12
    w = SCREEN_W - SIDEBAR_X - 22
    card = pygame.Rect(x0, y, w, 92)
    _panel(client.screen, card, NAVY_CARD, GOLD, radius=10, width=2, ornate=True)
    # Character face medallion
    portrait_size = 64
    px = card.x + 10
    py = card.y + (card.h - portrait_size) // 2
    client.screen.blit(_player_portrait(client, portrait_size), (px, py))
    text_x = px + portrait_size + 10
    name = (client.player or {}).get("name") or "Adventurer"
    level = client.player_combat_level()
    _blit(client, client.font, _fit_text(client.font, name, card.right - text_x - 100), (text_x, card.y + 10), INK)
    frac, _lvl = _xp_fraction(client)
    level_line = _text(client, client.font_tiny, f"Combat {level}  ·  {int(frac * 100)}%", GOLD)
    client.screen.blit(level_line, (text_x, card.y + 32))
    settings = pygame.Rect(SCREEN_W - 100, card.y + 8, 86, 24)
    _panel(client.screen, settings, NAVY_HI, GOLD, radius=6, width=2)
    _gear_mark(client.screen, settings.x + 12, settings.centery)
    label = _text(client, client.font_tiny, "Settings", GOLD)
    client.screen.blit(label, (settings.x + 24, settings.centery - label.get_height() // 2))
    # Quick logout under Settings — Menu → Logout stays as the secondary path.
    logout = pygame.Rect(settings.x, settings.bottom + 4, settings.w, 24)
    _panel(client.screen, logout, (70, 32, 32), DANGER_RED, radius=6, width=2)
    logout_l = _text(client, client.font_tiny, "Logout", INK)
    client.screen.blit(logout_l, (logout.centerx - logout_l.get_width() // 2,
                                  logout.centery - logout_l.get_height() // 2))
    # XP bar under the level line (stops before the Settings/Logout column)
    bar = pygame.Rect(text_x, card.y + 50, max(40, settings.x - text_x - 8), 9)
    _fill_bar(client.screen, bar, frac, GOLD, radius=4)
    # Title / deed ribbon (guild name or best quest deed)
    ribbon = pygame.Rect(text_x, card.y + 64, max(40, settings.x - text_x - 8), 20)
    _panel(client.screen, ribbon, (42, 32, 58), GOLD, radius=5, width=1)
    _blit(client, client.font_tiny, _fit_text(client.font_tiny, _title(client), ribbon.w - 12),
          (ribbon.x + 8, ribbon.y + 3), GOLD_BRIGHT)
    rects["settings"] = settings
    rects["header_logout"] = logout
    client.sidebar_settings_rect = settings
    client.logout_btn_rect = logout
    return card.bottom + 6


def _gear_mark(screen, cx, cy):
    """Small gear, the old settings mark."""
    pygame.draw.circle(screen, GOLD, (cx, cy), 6, 2)
    pygame.draw.circle(screen, GOLD, (cx, cy), 2)
    for dx, dy in ((0, -8), (6, -6), (8, 0), (6, 6), (0, 8), (-6, 6), (-8, 0), (-6, -6)):
        pygame.draw.line(screen, GOLD, (cx + dx // 2, cy + dy // 2), (cx + dx, cy + dy), 2)


def _draw_hitpoints(client, y):
    """Current life on the sidebar. Green above half, orange to a quarter, then red."""
    _mw, _mh, sidebar_x, screen_w, _sh = _layout()
    player = client.player or {}
    hp = int(player.get("hp") or 0)
    max_hp = max(1, int(player.get("max_hp") or 1))
    col, pct = client.hp_tone(hp, max_hp)
    x0 = sidebar_x + 12
    row = pygame.Rect(x0, y, screen_w - sidebar_x - 22, 32)
    _panel(client.screen, row, NAVY_CARD, GOLD_DIM, radius=7, width=1)
    _blit(client, client.font_tiny, "Hitpoints", (row.x + 10, row.y + 3), GOLD)
    value = _text(client, client.font_tiny, f"{hp} / {max_hp}", col)
    client.screen.blit(value, (row.right - value.get_width() - 10, row.y + 3))
    bar = pygame.Rect(row.x + 10, row.y + 18, row.w - 20, 9)
    _fill_bar(client.screen, bar, pct, col, radius=4)
    return row.bottom + 5


def _draw_currencies(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 12
    w = SCREEN_W - SIDEBAR_X - 22
    row = pygame.Rect(x0, y, w, 28)
    _panel(client.screen, row, NAVY_CARD, GOLD_DIM, radius=7)
    coins = int((client.player or {}).get("coins") or 0)
    bank = int((client.player or {}).get("bank_coins") or 0)
    if not bank:
        bank = int((getattr(client, "bank", None) or {}).get("bank_coins") or 0)
    # Coin · gems · vault — guild already sits on the header ribbon.
    pygame.draw.circle(client.screen, GOLD_BRIGHT, (row.x + 14, row.centery), 4)
    pygame.draw.circle(client.screen, GOLD_DIM, (row.x + 14, row.centery), 4, 1)
    _blit(client, client.font_tiny, f"{coins:,}", (row.x + 22, row.y + 6), GOLD)
    pygame.draw.circle(client.screen, (140, 190, 255), (row.x + 108, row.centery), 4)
    _blit(client, client.font_tiny, str(_gem_count(client)), (row.x + 116, row.y + 6), (160, 200, 255))
    pygame.draw.rect(client.screen, GOLD_DIM,
                     pygame.Rect(row.x + 168, row.centery - 4, 8, 8), border_radius=2)
    _blit(client, client.font_tiny, f"{bank:,}", (row.x + 180, row.y + 6), MUTED)
    return row.bottom + 5


GUILD_CHARTER_COST = 10_000


def _clan(client):
    return getattr(client, "clan_info", None) or {}


def _guild_label(client):
    name = str((_clan(client).get("name") or "")).strip()
    return name if name else "No guild"


def _guild_send(client, text):
    client.net.send("CHAT", text=text)


_GUILD_PROMPTS = {
    "create": {
        "title": "Create a guild",
        "hint": "Name: 3–20 letters or numbers (spaces OK).",
        "placeholder": "Guild name",
        "cmd": "/guild create",
        "max_len": 20,
    },
    "invite": {
        "title": "Invite a player",
        "hint": "Type their character name exactly.",
        "placeholder": "Player name",
        "cmd": "/guild invite",
        "max_len": 24,
    },
    "deposit": {
        "title": "Deposit coins",
        "hint": "Taken from your bank vault into the guild treasury.",
        "placeholder": "Amount",
        "cmd": "/guild deposit",
        "max_len": 12,
        "numeric": True,
    },
    "withdraw": {
        "title": "Withdraw coins",
        "hint": "Goes to your bank vault. Daily limit by rank.",
        "placeholder": "Amount",
        "cmd": "/guild withdraw",
        "max_len": 12,
        "numeric": True,
    },
}


def open_guild_prompt(client, kind):
    """Centered modal for create / invite / deposit / withdraw."""
    spec = _GUILD_PROMPTS.get(kind)
    if not spec:
        return
    if getattr(client, "chat_typing", False) and hasattr(client, "_end_chat_typing"):
        client._end_chat_typing()
    client.guild_prompt = {
        "kind": kind,
        "title": spec["title"],
        "hint": spec["hint"],
        "placeholder": spec["placeholder"],
        "cmd": spec["cmd"],
        "max_len": int(spec.get("max_len") or 24),
        "numeric": bool(spec.get("numeric")),
        "value": "",
    }
    client.guild_prompt_rects = {}
    pygame.key.start_text_input()


def close_guild_prompt(client):
    if getattr(client, "guild_prompt", None):
        client.guild_prompt = None
        client.guild_prompt_rects = {}
        pygame.key.stop_text_input()


def submit_guild_prompt(client):
    prompt = getattr(client, "guild_prompt", None) or {}
    raw = str(prompt.get("value") or "").strip()
    if not raw:
        return
    if prompt.get("numeric"):
        digits = raw.replace(",", "").replace(" ", "")
        if not digits.isdigit() or int(digits) <= 0:
            client.add_chat("Enter a whole number greater than zero.", color=DANGER_RED)
            return
        raw = str(int(digits))
    cmd = f"{prompt.get('cmd')} {raw}"
    close_guild_prompt(client)
    _guild_send(client, cmd)


def handle_guild_prompt_key(client, event):
    """True if the guild modal consumed this key event."""
    prompt = getattr(client, "guild_prompt", None)
    if not prompt:
        return False
    if event.key == pygame.K_ESCAPE:
        close_guild_prompt(client)
        return True
    if event.key == pygame.K_RETURN:
        submit_guild_prompt(client)
        return True
    if event.key == pygame.K_BACKSPACE:
        prompt["value"] = str(prompt.get("value") or "")[:-1]
        return True
    ch = event.unicode or ""
    if not ch or not ch.isprintable():
        return True
    if prompt.get("numeric") and ch not in "0123456789,":
        return True
    cur = str(prompt.get("value") or "")
    if len(cur) >= int(prompt.get("max_len") or 24):
        return True
    prompt["value"] = cur + ch
    return True


def handle_guild_prompt_click(client, mx, my):
    """True if the click was on the guild modal (always swallows while open)."""
    prompt = getattr(client, "guild_prompt", None)
    if not prompt:
        return False
    rects = getattr(client, "guild_prompt_rects", None) or {}
    if rects.get("ok") and rects["ok"].collidepoint(mx, my):
        submit_guild_prompt(client)
        return True
    if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
        close_guild_prompt(client)
        return True
    # Clicking the dimmer / box keeps focus; don't fall through to inventory.
    return True


def draw_guild_prompt(client):
    prompt = getattr(client, "guild_prompt", None)
    if not prompt:
        return
    _mw, _mh, _sx, screen_w, screen_h = _layout()
    # Dim the world + sidebar so the modal is obvious.
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((6, 8, 14, 160))
    client.screen.blit(veil, (0, 0))
    box = pygame.Rect(0, 0, 420, 210)
    box.center = (screen_w // 2, screen_h // 2)
    _panel(client.screen, box, NAVY_CARD, GOLD, radius=10, width=2, ornate=True)
    _blit(client, client.font_small, prompt.get("title") or "Guild", (box.x + 20, box.y + 18), GOLD)
    _blit(client, client.font_tiny,
          _fit_text(client.font_tiny, prompt.get("hint") or "", box.w - 40),
          (box.x + 20, box.y + 48), MUTED)
    field = pygame.Rect(box.x + 20, box.y + 78, box.w - 40, 36)
    _panel(client.screen, field, NAVY, GOLD, radius=6, width=2)
    shown = str(prompt.get("value") or "")
    if shown:
        _blit(client, client.font_small, shown, (field.x + 10, field.y + 8), INK)
    else:
        _blit(client, client.font_small, prompt.get("placeholder") or "",
              (field.x + 10, field.y + 8), MUTED)
    # Caret
    if int(pygame.time.get_ticks() / 400) % 2 == 0:
        caret_x = field.x + 10 + client.font_small.size(shown)[0]
        pygame.draw.line(client.screen, GOLD, (caret_x, field.y + 8), (caret_x, field.bottom - 8), 2)
    ok = pygame.Rect(box.x + 20, box.bottom - 52, 120, 34)
    cancel = pygame.Rect(box.right - 140, box.bottom - 52, 120, 34)
    _panel(client.screen, ok, (36, 70, 48), SAFE_GREEN, radius=6, width=2)
    _panel(client.screen, cancel, (70, 40, 40), DANGER_RED, radius=6, width=2)
    ok_l = _text(client, client.font_small, "Confirm", INK)
    cancel_l = _text(client, client.font_small, "Cancel", INK)
    client.screen.blit(ok_l, (ok.centerx - ok_l.get_width() // 2, ok.centery - ok_l.get_height() // 2))
    client.screen.blit(cancel_l, (cancel.centerx - cancel_l.get_width() // 2,
                                  cancel.centery - cancel_l.get_height() // 2))
    tip = _text(client, client.font_tiny, "Enter to confirm · Esc to cancel", MUTED)
    client.screen.blit(tip, (box.centerx - tip.get_width() // 2, box.bottom - 70))
    client.guild_prompt_rects = {"box": box, "field": field, "ok": ok, "cancel": cancel}


_GUILD_TABS = (("home", "Home"), ("members", "Roster"), ("bank", "Bank"), ("board", "Ranks"))
_RANK_PIP = {
    "Leader": GOLD,
    "Officer": (190, 200, 220),
    "Member": MUTED,
    "Recruit": (110, 150, 185),
}


def _guild_member_name(line):
    line = str(line or "")
    if line.endswith(")") and " (" in line:
        return line.rsplit(" (", 1)[0]
    return line


def _guild_member_rank(line):
    line = str(line or "")
    if line.endswith(")") and " (" in line:
        return line.rsplit(" (", 1)[1][:-1]
    return "Member"


def _guild_btn(client, rects, key, label, rect, style="secondary"):
    """style: primary | secondary | quiet | danger — omit the button instead of greying it."""
    ornate = False
    if style == "primary":
        fill, border, ink, width = (48, 40, 18), GOLD, INK, 2
        ornate = True
    elif style == "danger":
        fill, border, ink, width = (48, 22, 24), DANGER_RED, (230, 190, 190), 1
    elif style == "quiet":
        fill, border, ink, width = NAVY, GOLD_DIM, MUTED, 1
    else:
        fill, border, ink, width = NAVY_HI, GOLD, INK, 1
    _panel(client.screen, rect, fill, border, radius=6, width=width, ornate=ornate)
    surf = _text(client, client.font_tiny, label, ink)
    client.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                              rect.centery - surf.get_height() // 2))
    rects.setdefault("guild_btns", {})[key] = rect


def _draw_guild_tabs(client, x0, yy, w, rects):
    tab = getattr(client, "guild_tab", "home") or "home"
    valid = {k for k, _ in _GUILD_TABS}
    if tab not in valid:
        tab = "home"
        client.guild_tab = tab
    n = len(_GUILD_TABS)
    gap = 4
    tw = max(40, (w - gap * (n - 1)) // n)
    boxes = {}
    for i, (key, label) in enumerate(_GUILD_TABS):
        rect = pygame.Rect(x0 + i * (tw + gap), yy, tw, 26)
        on = tab == key
        _panel(client.screen, rect, NAVY_HI if on else NAVY, GOLD if on else GOLD_DIM,
               radius=5, width=2 if on else 1)
        surf = _text(client, client.font_tiny, label, INK if on else MUTED)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                  rect.centery - surf.get_height() // 2))
        boxes[key] = rect
    rects["guild_tabs"] = boxes
    return yy + 32


def _draw_guild_empty(client, x0, yy, w, bottom, rects):
    _blit(client, client.font_small, "Guild", (x0, yy), GOLD)
    yy += 22
    invite = (_clan(client) or {}).get("invite")
    if invite:
        banner = pygame.Rect(x0, yy, w, 86)
        _panel(client.screen, banner, (36, 32, 18), GOLD, radius=8, width=2, ornate=True)
        who = invite.get("from") or "Someone"
        gname = invite.get("name") or "a guild"
        secs = int(invite.get("expires_in") or 0)
        _blit(client, client.font_small,
              _fit_text(client.font_small, f"Invite · {gname}", w - 20),
              (banner.x + 10, banner.y + 8), GOLD)
        _blit(client, client.font_tiny,
              _fit_text(client.font_tiny, f"From {who} · {secs}s left", w - 20),
              (banner.x + 10, banner.y + 28), MUTED)
        bw = (w - 28) // 2
        _guild_btn(client, rects, "accept", "Accept",
                   pygame.Rect(banner.x + 10, banner.bottom - 36, bw, 28), "primary")
        _guild_btn(client, rects, "decline", "Decline",
                   pygame.Rect(banner.x + 18 + bw, banner.bottom - 36, bw, 28), "danger")
        yy = banner.bottom + 14
    else:
        _blit(client, client.font_tiny, "Found a company, or wait for an invite.",
              (x0, yy), MUTED)
        yy += 18

    _guild_btn(client, rects, "create", "Create guild…",
               pygame.Rect(x0, yy, w, 32), "primary")
    yy += 40
    _blit(client, client.font_tiny,
          f"Charter {GUILD_CHARTER_COST:,} bank coins · Ysolde has Guild Basics.",
          (x0, yy), MUTED)
    yy += 22
    _guild_btn(client, rects, "help", "Chat help",
               pygame.Rect(x0, yy, w // 2 - 4, 26), "quiet")


def _draw_guild_home(client, clan, x0, yy, w, bottom, rects):
    rank = clan.get("rank") or "Member"
    can_invite = rank in ("Leader", "Officer")
    can_hire = rank in ("Leader", "Officer")
    challenge = str(clan.get("challenge") or "").strip()
    if challenge:
        _blit(client, client.font_tiny,
              _fit_text(client.font_tiny, f"Challenge · {challenge}", w - 8),
              (x0, yy), (160, 190, 140))
        yy += 16
    _blit(client, client.font_tiny,
          f"Recruits {clan.get('recruits_active', 0)}/{clan.get('max_recruits', 8)}"
          f"  ·  Bank {int(clan.get('bank_coins') or 0):,}",
          (x0, yy), MUTED)
    yy += 20
    if can_invite:
        _guild_btn(client, rects, "invite", "Invite player…",
                   pygame.Rect(x0, yy, w, 30), "primary")
        yy += 38
    if can_hire and yy + 56 < bottom - 36:
        _blit(client, client.font_tiny, "Hire recruit · 5,000 from bank", (x0, yy), MUTED)
        yy += 16
        tw = (w - 16) // 3
        for i, role in enumerate(("Guard", "Squire", "Steward")):
            _guild_btn(client, rects, f"hire_{role.lower()}", role,
                       pygame.Rect(x0 + i * (tw + 8), yy, tw, 26), "secondary")
        yy += 34
    _blit(client, client.font_tiny, "Members and bank have their own tabs.",
          (x0, yy), MUTED)


def _draw_guild_members(client, clan, x0, yy, w, bottom, rects):
    rank = clan.get("rank") or "Member"
    can_manage = rank in ("Leader", "Officer")
    members = list(clan.get("members") or [])
    selected = getattr(client, "guild_selected", None)
    inspector_h = 0
    if selected and can_manage:
        inspector_h = 78 if rank == "Leader" else 52
    list_bottom = bottom - 36 - inspector_h
    row_h = 22
    visible = max(3, (list_bottom - yy) // row_h)
    max_scroll = max(0, len(members) - visible)
    scroll = max(0, min(max_scroll, int(getattr(client, "guild_scroll", 0) or 0)))
    client.guild_scroll = scroll
    if can_manage:
        _blit(client, client.font_tiny, "Click a member for officer tools", (x0, yy), MUTED)
        yy += 16
    for line in members[scroll:scroll + visible]:
        name = _guild_member_name(line)
        mrank = _guild_member_rank(line)
        rect = pygame.Rect(x0, yy, w, row_h - 2)
        on = selected == name
        _panel(client.screen, rect, NAVY_HI if on else NAVY, GOLD if on else GOLD_DIM, radius=4)
        pip = _RANK_PIP.get(mrank, MUTED)
        pygame.draw.circle(client.screen, pip, (rect.x + 10, rect.centery), 4)
        _blit(client, client.font_tiny, _fit_text(client.font_tiny, name, w - 78),
              (rect.x + 20, rect.y + 3), INK if on else MUTED)
        rank_s = _text(client, client.font_tiny, mrank[:7], pip)
        client.screen.blit(rank_s, (rect.right - rank_s.get_width() - 8,
                                    rect.centery - rank_s.get_height() // 2))
        rects["guild_members"][name] = rect
        yy += row_h
    if max_scroll:
        _blit(client, client.font_tiny,
              f"{scroll + 1}–{min(len(members), scroll + visible)} of {len(members)}",
              (x0, yy), MUTED)
        if scroll > 0:
            _guild_btn(client, rects, "scroll_up", "▲",
                       pygame.Rect(x0 + w - 76, yy - 2, 34, 20), "quiet")
        if scroll < max_scroll:
            _guild_btn(client, rects, "scroll_down", "▼",
                       pygame.Rect(x0 + w - 38, yy - 2, 34, 20), "quiet")
        yy += 22
    if selected and can_manage:
        panel = pygame.Rect(x0, bottom - 36 - inspector_h, w, inspector_h - 4)
        _panel(client.screen, panel, NAVY_CARD, GOLD_DIM, radius=6)
        _blit(client, client.font_tiny,
              _fit_text(client.font_tiny, selected, w - 16),
              (panel.x + 8, panel.y + 6), GOLD)
        tw = (w - 28) // 3
        by = panel.y + 24
        _guild_btn(client, rects, "promote", "Promote",
                   pygame.Rect(panel.x + 8, by, tw, 24), "secondary")
        _guild_btn(client, rects, "demote", "Demote",
                   pygame.Rect(panel.x + 12 + tw, by, tw, 24), "quiet")
        _guild_btn(client, rects, "kick", "Kick",
                   pygame.Rect(panel.x + 16 + 2 * tw, by, tw, 24), "danger")
        if rank == "Leader" and selected != (client.player or {}).get("name"):
            _guild_btn(client, rects, "leader", "Pass leader",
                       pygame.Rect(panel.x + 8, by + 28, w - 16, 24), "danger")


def _draw_guild_bank(client, clan, x0, yy, w, bottom, rects):
    rank = clan.get("rank") or "Member"
    bank = int(clan.get("bank_coins") or 0)
    card = pygame.Rect(x0, yy, w, 64)
    _panel(client.screen, card, NAVY_CARD, GOLD, radius=8, width=2, ornate=True)
    _blit(client, client.font_tiny, "Guild treasury", (card.x + 12, card.y + 10), MUTED)
    amount = _text(client, client.font_small, f"{bank:,}", GOLD)
    client.screen.blit(amount, (card.x + 12, card.y + 28))
    coin = _text(client, client.font_tiny, "coins", MUTED)
    client.screen.blit(coin, (card.x + 16 + amount.get_width(), card.y + 34))
    yy = card.bottom + 12
    _guild_btn(client, rects, "deposit", "Deposit…",
               pygame.Rect(x0, yy, w, 30), "primary")
    yy += 36
    qw = (w - 8) // 2
    _guild_btn(client, rects, "deposit_1k", "+1,000",
               pygame.Rect(x0, yy, qw, 26), "quiet")
    _guild_btn(client, rects, "deposit_10k", "+10,000",
               pygame.Rect(x0 + qw + 8, yy, qw, 26), "quiet")
    yy += 34
    if rank != "Recruit":
        _guild_btn(client, rects, "withdraw", "Withdraw…",
                   pygame.Rect(x0, yy, w, 30), "secondary")
        yy += 36
    else:
        _blit(client, client.font_tiny, "Recruits cannot withdraw.", (x0, yy), MUTED)
        yy += 18
    _blit(client, client.font_tiny, "From your bank vault · daily withdraw by rank.",
          (x0, yy), MUTED)


def _draw_guild_board(client, clan, x0, yy, w, bottom, rects):
    """Member leaderboard by total skill level, then total XP."""
    g_lvl = int(clan.get("guild_total_level") or 0)
    g_xp = int(clan.get("guild_total_xp") or 0)
    card = pygame.Rect(x0, yy, w, 52)
    _panel(client.screen, card, NAVY_CARD, GOLD, radius=6, width=2, ornate=True)
    _blit(client, client.font_tiny, "Guild skill board", (card.x + 10, card.y + 6), MUTED)
    _blit(client, client.font_tiny, f"Σ levels {g_lvl:,}", (card.x + 10, card.y + 22), GOLD)
    _blit(client, client.font_tiny, f"Σ XP {g_xp:,}", (card.x + 10, card.y + 36), GOLD)
    yy = card.bottom + 8
    _blit(client, client.font_tiny, "Ranked by total level, then XP", (x0, yy), MUTED)
    yy += 14
    board = list(clan.get("board") or [])
    if not board:
        _blit(client, client.font_tiny, "No members to rank yet.", (x0, yy), MUTED)
        return
    row_h = 22
    visible = max(3, (bottom - yy - 4) // row_h)
    scroll = max(0, min(max(0, len(board) - visible),
                        int(getattr(client, "guild_scroll", 0) or 0)))
    client.guild_scroll = scroll
    my_name = (client.player or {}).get("name") or ""
    for i, entry in enumerate(board[scroll:scroll + visible]):
        place = scroll + i + 1
        name = str(entry.get("name") or "?")
        mrank = str(entry.get("rank") or "Member")
        lvl = int(entry.get("total_level") or 0)
        xp = int(entry.get("total_xp") or 0)
        rect = pygame.Rect(x0, yy, w, row_h - 2)
        me = name == my_name
        _panel(client.screen, rect, NAVY_HI if me else NAVY, GOLD if me else GOLD_DIM, radius=4)
        pip = _RANK_PIP.get(mrank, MUTED)
        pygame.draw.circle(client.screen, pip, (rect.x + 10, rect.centery), 4)
        place_c = GOLD if place <= 3 else MUTED
        _blit(client, client.font_tiny, f"{place}.", (rect.x + 18, rect.y + 3), place_c)
        _blit(client, client.font_tiny, _fit_text(client.font_tiny, name, w - 120),
              (rect.x + 36, rect.y + 3), GOLD if me else INK)
        right = _text(client, client.font_tiny, f"Lv {lvl}  {xp:,}", GOLD if me else MUTED)
        client.screen.blit(right, (rect.right - right.get_width() - 6,
                                   rect.centery - right.get_height() // 2))
        yy += row_h
    if len(board) > visible:
        if scroll > 0:
            _guild_btn(client, rects, "scroll_up", "▲",
                       pygame.Rect(x0 + w - 76, min(yy, bottom - 22), 34, 20), "quiet")
        if scroll + visible < len(board):
            _guild_btn(client, rects, "scroll_down", "▼",
                       pygame.Rect(x0 + w - 38, min(yy, bottom - 22), 34, 20), "quiet")


def _draw_guild(client, y, bottom, rects):
    """Guild panel: empty/invite state, or Home / Members / Bank tabs."""
    clan = _clan(client)
    x0 = _body_x()
    w = _body_w()
    rects["guild_btns"] = {}
    rects["guild_members"] = {}
    rects["guild_tabs"] = {}
    yy = y + 4

    if not clan.get("name"):
        _draw_guild_empty(client, x0, yy, w, bottom, rects)
        return

    rank = clan.get("rank") or "Member"
    count = int(clan.get("count") or 0)
    cap = int(clan.get("max_members") or 25)
    _blit(client, client.font_small,
          _fit_text(client.font_small, clan.get("name") or "Guild", w - 8),
          (x0, yy), GOLD)
    yy += 18
    _blit(client, client.font_tiny,
          f"{rank}  ·  {count}/{cap}  ·  Leader {clan.get('leader') or '?'}",
          (x0, yy), MUTED)
    yy += 16
    yy = _draw_guild_tabs(client, x0, yy, w, rects)

    tab = getattr(client, "guild_tab", "home") or "home"
    footer_y = bottom - 30
    body_bottom = footer_y - 6
    if tab == "members":
        _draw_guild_members(client, clan, x0, yy, w, body_bottom, rects)
    elif tab == "bank":
        _draw_guild_bank(client, clan, x0, yy, w, body_bottom, rects)
    elif tab == "board":
        _draw_guild_board(client, clan, x0, yy, w, body_bottom, rects)
    else:
        _draw_guild_home(client, clan, x0, yy, w, body_bottom, rects)

    bw = (w - 8) // 2
    _guild_btn(client, rects, "leave", "Leave",
               pygame.Rect(x0, footer_y, bw, 26), "danger")
    _guild_btn(client, rects, "help", "Help",
               pygame.Rect(x0 + bw + 8, footer_y, bw, 26), "quiet")


def _guild_click(client, key):
    selected = getattr(client, "guild_selected", None)
    if key == "create":
        open_guild_prompt(client, "create")
        return
    if key == "accept":
        _guild_send(client, "/guild accept")
        # Follow-up sync in case the accept reply races the panel.
        try:
            client.net.send("GUILD_SYNC")
        except Exception:
            pass
        return
    if key == "decline":
        _guild_send(client, "/guild decline")
        try:
            client.net.send("GUILD_SYNC")
        except Exception:
            pass
        return
    if key == "invite":
        open_guild_prompt(client, "invite")
        return
    if key == "deposit":
        open_guild_prompt(client, "deposit")
        return
    if key == "deposit_1k":
        _guild_send(client, "/guild deposit 1000")
        return
    if key == "deposit_10k":
        _guild_send(client, "/guild deposit 10000")
        return
    if key == "withdraw":
        open_guild_prompt(client, "withdraw")
        return
    if key == "leave":
        _guild_send(client, "/guild leave")
        client.guild_selected = None
        client.guild_tab = "home"
        return
    if key == "help":
        _guild_send(client, "/guild help")
        return
    if key == "scroll_up":
        client.guild_scroll = max(0, int(getattr(client, "guild_scroll", 0) or 0) - 1)
        return
    if key == "scroll_down":
        client.guild_scroll = int(getattr(client, "guild_scroll", 0) or 0) + 1
        return
    if key in ("promote", "demote", "kick", "leader") and selected:
        _guild_send(client, f"/guild {key} {selected}")
        return
    if key.startswith("hire_"):
        role = key.split("_", 1)[1].title()
        _guild_send(client, f"/guild hire {role}")
        return


def _next_open_quest_step(client):
    """First incomplete non-endgame quest (respecting requires), or Elowen when ready."""
    quests = client.quests or {}
    if all_other_quests_complete(client):
        oath = quests.get("fairy_oath") or {}
        if (oath.get("status") or "not_started") != "complete":
            return {
                "title": "The Royal Challenge",
                "detail": "Lady Elowen Moonwhisper — Fairy Glade",
                "hint": "Endgame oath — combat, castle, guild, then claim the Crown",
                "npc": "elowen_moonwhisper",
            }
        return None
    for qid, qdef in QUESTS.items():
        if qid == "fairy_oath":
            continue
        req = qdef.get("requires")
        if req and (quests.get(req) or {}).get("status") != "complete":
            continue
        status = (quests.get(qid) or {}).get("status") or "not_started"
        if status == "complete":
            continue
        giver = qdef.get("giver")
        npc = next((n for n in NPCS if n.get("id") == giver), None)
        where = (npc.get("name") if npc else None) or "the quest giver"
        name = qdef.get("name") or qid
        what = (qdef.get("description") or "").strip() or f"Talk to {where} to accept"
        return {
            "title": name,
            "detail": what,
            "hint": f"Accept from {where} · Go sets the path",
            "npc": giver,
        }
    return None


def _no_quest_step(client):
    """One concrete next step for a player with no active quest.

    Ordered by what actually blocks a fresh character: the tutorial, then a
    weapon in hand, then the starter quest, then food, then the next open
    quest. The Royal Challenge is only suggested after every other quest.
    """
    welcome = getattr(client, "welcome", None) or {}
    # One spine: Tamsin → Sarah (eat) → Miriam. Don't keep saying "get kit" after claim.
    if welcome.get("show_path") and not welcome.get("claimed"):
        return {"title": "Get your starter kit", "detail": "Warden Tamsin, by the crossroads",
                "hint": "Follow the gold trail — she explains the basics", "npc": "warden_tamsin"}
    player = client.player or {}
    weapon = (player.get("equipment") or {}).get("weapon")
    if not weapon:
        return {"title": "You're fighting bare-handed", "detail": "Equip a weapon from your bag (E)",
                "hint": "An axe or pick works too — click it to wield", "npc": None}
    if welcome.get("show_path") and welcome.get("claimed") and not welcome.get("eat_done"):
        return {"title": "Learn food & HP", "detail": "Innkeeper Sarah, south of the square",
                "hint": "Press R / Eat — food keeps you alive in fights", "npc": "innkeeper_sarah"}
    starter = (client.quests or {}).get("rat_problem") or {}
    if (starter.get("status") or "not_started") != "complete":
        # A fresh client has quests == {} (no QUEST_LOG yet), which reads as
        # not_started — the right advice for a brand-new character. Completing
        # some other quest does not satisfy this specific milestone.
        return {"title": "Find Elder Miriam", "detail": "North-west cottage — your first quest",
                "hint": "Click her, then press A to accept", "npc": "elder_miriam"}
    has_food = any(is_food((entry or {}).get("item_id")) or (entry or {}).get("item_id") == "food_bag"
                   for entry in (player.get("inventory") or {}).values())
    if not has_food:
        return {"title": "Carry some food", "detail": "Cook fish at a hearth, or buy food at a shop",
                "hint": "Innkeeper Sarah (south) shows Eat / R — or cook fish at a hearth",
                "npc": "innkeeper_sarah"}
    nxt = _next_open_quest_step(client)
    if nxt:
        return nxt
    return {"title": "Follow the trail", "detail": "Your quest card lists its next step",
            "hint": "Press Q for the quest journal · H for controls", "npc": None}


def _quest_finish_hint(client, qid, status):
    """Plain-English 'what to do next / how this finishes' for the quest card."""
    qdef = QUESTS.get(qid) or {}
    giver = next((n for n in NPCS if n.get("id") == qdef.get("giver")), None) or {}
    giver_name = giver.get("name") or "the quest giver"
    qtype = qdef.get("type")
    if status == "ready":
        return f"Done — talk to {giver_name} to turn in"
    if qtype == "kill":
        return f"Defeat them, then return to {giver_name}"
    if qtype in ("collect", "collect_multi"):
        return f"Gather these, then return to {giver_name}"
    if qtype == "find_npc":
        target = next((n for n in NPCS if n.get("id") == qdef.get("target")), None) or {}
        who = target.get("name") or "them"
        return f"Speak with {who}, then return to {giver_name}"
    if qtype == "guild":
        return f"Join/create a guild + deposit coins, then return to {giver_name}"
    if qtype == "oath":
        return "Endgame goals — finish all four, then return to Elowen"
    if qtype == "gift":
        return f"Talk to {giver_name} — reward is granted on accept"
    desc = (qdef.get("description") or "").strip()
    return desc or f"Return to {giver_name} when finished"


def _draw_go_button(client, card, rects, npc_id=None, dest=None):
    """Green Go control — NPC talk target and/or world destination."""
    track = pygame.Rect(card.right - 58, card.bottom - 28, 50, 22)
    _panel(client.screen, track, NAVY_HI, SAFE_GREEN, radius=4)
    label = _text(client, client.font_tiny, "Go", INK)
    client.screen.blit(label, (track.centerx - label.get_width() // 2,
                               track.centery - label.get_height() // 2))
    rects["quest_track"] = {"rect": track, "npc_id": npc_id}
    if dest and dest.get("x") is not None:
        rects["quest_track_dest"] = {
            "rect": dest, "x": dest["x"], "y": dest["y"],
            "label": dest.get("label") or "Objective",
        }


def _draw_quest_card(client, y, rects):
    """Sidebar quest briefing: name, objective progress, and how to finish."""
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 12
    w = SCREEN_W - SIDEBAR_X - 22
    card = pygame.Rect(x0, y, w, 108)
    quests_open = client.hud_focus == "quests"
    _panel(client.screen, card, NAVY_HI if quests_open else NAVY_CARD,
           GOLD_BRIGHT if quests_open else GOLD, radius=9, width=2, ornate=True)
    text_w = w - 70  # leave room for Go
    quest = _current_quest(client)
    if not quest:
        # No active quest — name the next NPC/step so Go can set a path.
        step = _no_quest_step(client)
        _blit(client, client.font_tiny, "NEXT STEP", (card.x + 8, card.y + 4), GOLD)
        _blit(client, client.font_small,
              _fit_text(client.font_small, step["title"], text_w),
              (card.x + 8, card.y + 18), INK)
        yy = card.y + 38
        for line in _wrap_text(client.font_tiny, step["detail"], text_w, max_lines=2):
            _blit(client, client.font_tiny, line, (card.x + 8, yy), GOLD)
            yy += 14
        _blit(client, client.font_tiny,
              _fit_text(client.font_tiny, step["hint"], text_w),
              (card.x + 8, card.bottom - 22), MUTED)
        if step.get("npc"):
            _draw_go_button(client, card, rects, npc_id=step["npc"])
    else:
        name, _desc, progress, need, status = quest
        qid = _tracked_quest_id(client)
        state = (client.quests or {}).get(qid) or {}
        qdef = QUESTS.get(qid) or {}
        header = "READY TO TURN IN" if status == "ready" else "CURRENT QUEST"
        _blit(client, client.font_tiny, header, (card.x + 8, card.y + 4), GOLD)
        _blit(client, client.font_small,
              _fit_text(client.font_small, name, text_w),
              (card.x + 8, card.y + 18), INK)

        objective = client._quest_objective_text(qid, state) if qid else _desc
        if status == "ready":
            giver = next((npc for npc in NPCS if npc.get("id") == qdef.get("giver")), {})
            objective = f"Return to {giver.get('name', 'the quest giver')}"
        # Prefer live objective; fall back to the quest description.
        if not (objective or "").strip():
            objective = (qdef.get("description") or "").strip()

        yy = card.y + 38
        obj_lines = _wrap_text(client.font_tiny, objective, text_w, max_lines=2)
        for line in obj_lines:
            _blit(client, client.font_tiny, line, (card.x + 8, yy), GOLD)
            yy += 14
        finish = _quest_finish_hint(client, qid, status) if qid else ""
        if need and status == "active":
            finish = f"{progress}/{need} · {finish}" if finish else f"Progress {progress}/{need}"
        _blit(client, client.font_tiny,
              _fit_text(client.font_tiny, finish, text_w),
              (card.x + 8, card.bottom - 22), MUTED)

        # Go → hand-in NPC, find-NPC target, or objective camp/travel spot.
        target_id = qdef.get("giver") if status == "ready" else None
        if qdef.get("type") == "find_npc" and status != "ready":
            target_id = qdef.get("target")
        dest = None
        if qid and status in ("active", "ready"):
            try:
                import new_player_guide
                spot = new_player_guide.quest_objective_dest(client, qid)
                if spot:
                    dest = {"x": spot[0], "y": spot[1], "label": spot[2]}
            except Exception:
                dest = None
        if not dest and qdef.get("type") == "kill" and status != "ready":
            camp = next((d for d in TRAVEL_DESTINATIONS
                         if d.get("kind") == "monster" and d.get("monster") == qdef.get("target")), None)
            if camp:
                dest = {"x": camp["x"], "y": camp["y"], "label": camp.get("label") or qdef.get("target")}
        if target_id or dest:
            _draw_go_button(client, card, rects, npc_id=target_id, dest=dest)
    rects["quest_card"] = card
    return card.bottom + 4


def _draw_system_tabs(client, y, rects):
    _mw, _mh, SIDEBAR_X, SCREEN_W, _sh = _layout()
    x0 = SIDEBAR_X + 12
    w = SCREEN_W - SIDEBAR_X - 22
    # Focus panels (Guild, Party, …) own the body — one back chip instead of Inv tabs.
    if client.hud_focus:
        label = {
            "guild": "Guild", "party": "Party", "events": "Events",
            "mounts": "Mounts", "lore": "Lore", "achievements": "Achievements",
            "quests": "Quests",
        }.get(client.hud_focus, "Panel")
        back = pygame.Rect(x0, y, w, 30)
        _panel(client.screen, back, NAVY_HI, GOLD, radius=7, width=2, ornate=True)
        surf = _text(client, client.font_tiny, f"← Inventory   ·   {label}", GOLD_BRIGHT)
        client.screen.blit(surf, (back.centerx - surf.get_width() // 2,
                                  back.centery - surf.get_height() // 2))
        # Click maps to inventory system handler, which clears focus.
        rects["systems"] = {"inventory": back}
        return y + 36
    tab_w = w // 4
    boxes = {}
    for i, (key, label) in enumerate(SYSTEMS):
        rect = pygame.Rect(x0 + i * tab_w, y, tab_w - 4, 32)
        active = client.hud_system == key and not client.hud_focus
        _panel(client.screen, rect,
               NAVY_HI if active else NAVY_CARD,
               GOLD if active else GOLD_DIM,
               radius=6, width=2 if active else 1, ornate=active)
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
    if focus == "quests":
        _draw_quests(client, y, bottom, rects)
        return
    if focus == "guild":
        _draw_guild(client, y, bottom, rects)
        return
    if focus in ("mounts", "party", "events"):
        messages = {
            "mounts": "No mounts yet.",
            "party": "You are not in a party.",
            "events": "No world event is active.",
        }
        _blit(client, client.font_small, messages[focus], (_body_x() + 8, y + 8), MUTED)
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
    return sidebar_x + 12


def _body_w():
    _mw, _mh, sidebar_x, screen_w, _sh = _layout()
    return screen_w - sidebar_x - 22


def _panel_blocking_hover(client):
    names = (
        "show_bank", "show_forge", "show_cook", "show_equipment", "show_help",
        "show_shop_panel", "show_skills", "show_pets", "show_travel",
        "drop_prompt", "dialogue",
    )
    return any(getattr(client, name, None) for name in names)


def _draw_inventory(client, y, bottom, rects):
    x0 = _body_x()
    # Capacity line ("47 / 96") removed — frees a row of bag space and
    # cuts scroll. Slot count still lives on the help / bag screens.
    filters = {}
    # Full words on the chips — abbreviations (Wpn/Arm/Mat) were unclear on quests.
    chip_labels = {
        "all": "All",
        "weapons": "Weapon",
        "armour": "Armour",
        "consumables": "Food",
        "materials": "Material",
        "quest": "Quest",
    }
    chip_w = (_body_w() - 6) // 3
    chip_h = 18
    chip_gap = 3
    for i, (key, _label) in enumerate(FILTERS):
        col, row = i % 3, i // 3
        rect = pygame.Rect(x0 + col * (chip_w + chip_gap), y + row * (chip_h + chip_gap), chip_w, chip_h)
        active = client.hud_filter == key
        _panel(client.screen, rect, NAVY_HI if active else NAVY, GOLD if active else GOLD_DIM, radius=4)
        label = chip_labels.get(key) or key.title()
        surf = _text(client, client.font_tiny, label, INK if active else MUTED)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                  rect.centery - surf.get_height() // 2))
        filters[key] = rect
    rects["filters"] = filters
    if filters:
        xs = [r.x for r in filters.values()]
        ys = [r.y for r in filters.values()]
        rights = [r.right for r in filters.values()]
        bottoms = [r.bottom for r in filters.values()]
        rects["inv_filters"] = pygame.Rect(min(xs), min(ys), max(rights) - min(xs), max(bottoms) - min(ys))
    y += 2 * (chip_h + chip_gap) + 4
    rows = _filtered_entries(client)
    cols = 4
    gap = 3
    scroll_w = 20
    grid_w = _body_w() - scroll_w - 4
    # Prefer fitting an extra visible row over oversized icons when height is tight.
    size_w = max(48, (grid_w - gap * (cols - 1)) // cols)
    slot_bottom = bottom - 34
    avail_h = max(size_w, slot_bottom - y)
    size = size_w
    for candidate in range(size_w, 47, -1):
        if avail_h // (candidate + gap) > avail_h // (size_w + gap):
            size = candidate
            break
    row_h = size + gap
    slots = {}
    hover = None
    import procedural_sprites_finished as sprites
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
    if not rows:
        # An empty bag (or an empty filter) used to leave a blank void with no
        # way to tell "nothing here" from "the panel is broken". Say which it
        # is, and what to do about it.
        filt = getattr(client, "hud_filter", "all")
        if filt == "all":
            msg = "Your bag is empty.  Click trees, rocks or fish to gather."
            hint = "Loot, food and coins you pick up appear here."
        else:
            msg = f"No {filt} in your bag."
            hint = "Press 'All' above to see everything."
        _blit(client, client.font_small, msg, (x0 + 4, y + 10), MUTED)
        _blit(client, client.font_tiny, hint, (x0 + 4, y + 30), GOLD_DIM)
    rects["inv_scroll_up"] = None
    rects["inv_scroll_down"] = None
    rects["inv_scroll_track"] = None
    rects["inv_scroll_thumb"] = None
    # Always reserve the bar column when content can overflow (or already does).
    if max_scroll or total_rows > visible_rows:
        bar_x = x0 + grid_w + 6
        up = pygame.Rect(bar_x, y, scroll_w, 22)
        down = pygame.Rect(bar_x, slot_bottom - 22, scroll_w, 22)
        track = pygame.Rect(bar_x, up.bottom + 2, scroll_w, max(24, down.y - up.bottom - 4))
        _panel(client.screen, up, NAVY_HI if scroll > 0 else NAVY, GOLD, radius=4, width=2)
        _panel(client.screen, down, NAVY_HI if scroll < max_scroll else NAVY, GOLD, radius=4, width=2)
        _blit(client, client.font_small, "▲", (up.centerx - 5, up.y + 1), INK if scroll > 0 else MUTED)
        _blit(client, client.font_small, "▼", (down.centerx - 5, down.y + 1), INK if scroll < max_scroll else MUTED)
        pygame.draw.rect(client.screen, (22, 28, 40), track, border_radius=5)
        pygame.draw.rect(client.screen, GOLD, track, 2, border_radius=5)
        thumb = None
        if max_scroll > 0 and track.h > 16:
            thumb_h = max(28, int(track.h * visible_rows / max(1, total_rows)))
            thumb_h = min(track.h - 4, thumb_h)
            travel = max(1, track.h - thumb_h - 4)
            thumb_y = track.y + 2 + int(travel * (scroll / max_scroll))
            thumb = pygame.Rect(track.x + 3, thumb_y, track.w - 6, thumb_h)
            pygame.draw.rect(client.screen, (90, 120, 70), thumb, border_radius=4)
            pygame.draw.rect(client.screen, (200, 220, 120), thumb, 2, border_radius=4)
            # Grip lines so it reads as a draggable handle.
            for gy in (thumb.centery - 4, thumb.centery, thumb.centery + 4):
                pygame.draw.line(
                    client.screen, (230, 240, 180),
                    (thumb.x + 4, gy), (thumb.right - 4, gy), 1,
                )
        page = f"{scroll + 1}/{max_scroll + 1}"
        page_s = _text(client, client.font_tiny, page, GOLD)
        client.screen.blit(page_s, (bar_x + (scroll_w - page_s.get_width()) // 2, down.bottom + 2))
        rects["inv_scroll_up"] = up
        rects["inv_scroll_down"] = down
        rects["inv_scroll_track"] = track
        rects["inv_scroll_thumb"] = thumb
        client.hud_inv_scroll_meta = {
            "track": track, "thumb": thumb, "max_scroll": max_scroll,
            "visible_rows": visible_rows, "total_rows": total_rows,
        }
    else:
        client.hud_inv_scroll_meta = None
    rects["actions"] = {}
    equip = pygame.Rect(x0, bottom - 28, _body_w(), 26)
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
    eq = (client.player or {}).get("equipment") or {}
    labels = (("tool_woodcutting", "Axe"), ("tool_mining", "Pick"), ("tool_fishing", "Net"))
    worn = []
    for key, short in labels:
        item_id = eq.get(key)
        if item_id:
            name = (ITEMS.get(item_id) or {}).get("name") or item_id
            worn.append(f"{short}: {name}")
        else:
            worn.append(f"{short}: —")
    _blit(client, client.font_tiny, "  ·  ".join(worn), (x0, y), MUTED)
    y += 18
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
    _blit(client, client.font_tiny, "Bulk storage and ammo containers", (x0, y), MUTED)
    y += 18
    boxes = {}
    player = client.player or {}

    # A quiver is both a container and worn ammunition. Keeping it out of the
    # normal inventory list made a loaded-but-unequipped quiver invisible.
    inventory = player.get("inventory") or {}
    quiver_slot = next(
        (int(slot) for slot, entry in inventory.items()
         if entry and entry.get("item_id") == "arrow_quiver"),
        None,
    )
    ammo_id = (player.get("equipment") or {}).get("ammo")
    quiver_equipped = ammo_id == "arrow_quiver"
    quiver_total = int(player.get("quiver_total") or 0)
    quiver = pygame.Rect(x0, y, _body_w(), 42)
    owned = quiver_equipped or quiver_slot is not None
    _panel(client.screen, quiver, NAVY_CARD, GOLD if owned else GOLD_DIM, radius=5)
    _blit(client, client.font_tiny, "Arrow Quiver", (quiver.x + 8, quiver.y + 5), INK if owned else MUTED)
    if quiver_equipped:
        detail, detail_col = f"Equipped · {quiver_total} arrows", SAFE_GREEN
    elif quiver_slot is not None:
        detail, detail_col = f"{quiver_total} stored · equip to fire", GOLD
    elif quiver_total:
        detail, detail_col = f"{quiver_total} stored · quiver missing", DANGER_RED
    else:
        detail, detail_col = "Not owned", MUTED
    _blit(client, client.font_tiny, detail, (quiver.x + 8, quiver.y + 22), detail_col)
    if quiver_slot is not None and not quiver_equipped:
        equip = pygame.Rect(quiver.right - 58, quiver.y + 9, 50, 24)
        _panel(client.screen, equip, NAVY_HI, SAFE_GREEN, radius=5)
        label = _text(client, client.font_tiny, "Equip", INK)
        client.screen.blit(label, (equip.centerx - label.get_width() // 2, equip.centery - label.get_height() // 2))
        rects["quiver_equip"] = {"rect": equip, "slot": quiver_slot}
    boxes["Arrow Quiver"] = quiver
    y += 44
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


def _draw_quests(client, y, bottom, rects):
    """Quest journal opened from the left Quests nav — highlighted while open."""
    x0 = _body_x()
    w = _body_w()
    qp = int((client.player or {}).get("quest_points") or 0)
    _blit(client, client.font_small, f"Quest journal  ·  {qp} QP", (x0, y), GOLD)
    _blit(client, client.font_tiny, "Click a quest to track it", (x0, y + 18), MUTED)
    y += 38
    order = {"ready": 0, "active": 1, "not_started": 2, "complete": 3}
    entries = []
    for qid, spec in QUESTS.items():
        info = (client.quests or {}).get(qid) or {"status": "not_started", "progress": 0}
        status = info.get("status") or "not_started"
        req = spec.get("requires")
        if status == "not_started" and req:
            needed = req if isinstance(req, (list, tuple)) else [req]
            if any(((client.quests or {}).get(r) or {}).get("status") != "complete" for r in needed):
                continue
        entries.append((qid, info, status, spec))
    entries.sort(key=lambda t: (order.get(t[2], 9), (t[3].get("name") or t[0])))
    rows = {}
    if not entries:
        _blit(client, client.font_tiny, "Talk to Elder Miriam (NW cottage) to begin.", (x0, y), MUTED)
        rects["quest_rows"] = rows
        return
    for qid, info, status, spec in entries:
        if y > bottom - 44:
            _blit(client, client.font_tiny, "…more in progress", (x0, y), GOLD_DIM)
            break
        rect = pygame.Rect(x0, y, w, 40)
        tracked = qid == getattr(client, "tracked_quest_id", None)
        fill = NAVY_HI if tracked or status == "ready" else NAVY_CARD
        border = GOLD_BRIGHT if tracked else (GOLD if status == "ready" else GOLD_DIM)
        _panel(client.screen, rect, fill, border, radius=5, width=2 if tracked else 1)
        title = spec.get("name") or qid.replace("_", " ").title()
        status_col = {
            "ready": GOLD, "active": INK, "complete": SAFE_GREEN, "not_started": MUTED,
        }.get(status, MUTED)
        _blit(client, client.font_tiny, _fit_text(client.font_tiny, title, w - 16),
              (rect.x + 8, rect.y + 4), status_col)
        label = {
            "not_started": "Available", "active": "In progress",
            "ready": "Ready to turn in", "complete": "Complete",
        }.get(status, status)
        if status in ("active", "ready"):
            obj = ""
            if hasattr(client, "_quest_objective_text"):
                obj = client._quest_objective_text(qid, info) or ""
            if obj:
                label = _fit_text(client.font_tiny, obj, w - 16)
        _blit(client, client.font_tiny, label, (rect.x + 8, rect.y + 20), MUTED)
        rows[qid] = rect
        y += 44
    rects["quest_rows"] = rows


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
    # Bottom of the drawer — utility row moved under ATK/STR/DEF/RNG/EAT.
    rect = pygame.Rect(sidebar_x + 12, screen_h - 36, screen_w - sidebar_x - 22, 28)
    active = bool(getattr(client, "show_skills", False))
    _panel(client.screen, rect, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM,
           radius=6, width=2 if active else 1, ornate=active)
    combat = client.player_combat_level()
    total = client.player_total_level()
    label = _text(client, client.font_small, f"Skills   Combat {combat}   Total {total}", INK)
    client.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))
    rects["skills"] = rect
    client.skills_btn_rect = rect


def _draw_utility_row(client, rects):
    """Legacy sidebar utility strip. Drawn panels put these under combat styles."""
    _mw, _mh, SIDEBAR_X, SCREEN_W, SCREEN_H = _layout()
    keys = (("mounts", "Mounts"), ("pets", "Pets"), ("lore", "Lore"), ("achievements", "Achieve"), ("menu", "Menu"))
    x0 = SIDEBAR_X + 12
    w = (SCREEN_W - SIDEBAR_X - 22) // len(keys)
    y = SCREEN_H - 38
    boxes = {}
    for i, (key, label) in enumerate(keys):
        rect = pygame.Rect(x0 + i * w, y, w - 4, 30)
        active = client.hud_focus == key or (key == "menu" and client.hud_menu)
        _panel(client.screen, rect, NAVY_HI if active else NAVY_CARD, GOLD if active else GOLD_DIM,
               radius=6, width=2 if active else 1, ornate=active)
        surf = _text(client, client.font_tiny, label[:6], INK if active else MUTED)
        client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
        boxes[key] = rect
    rects["utility"] = boxes


def _draw_menu(client, rects):
    """Help + Logout flyout anchored to the Menu button (combat bar or sidebar)."""
    menu_btn = (rects.get("utility") or {}).get("menu")
    if not menu_btn:
        return
    _mw, _mh, sx, sw, sh = _layout()
    # Prefer above the button; if that would cover the map poorly, still clamp.
    box_w, box_h = 170, 98
    box = pygame.Rect(menu_btn.centerx - box_w // 2, menu_btn.y - box_h - 8, box_w, box_h)
    if box.x < 8:
        box.x = 8
    if box.right > sw - 6:
        box.x = sw - box.w - 6
    if box.y < 6:
        box.y = menu_btn.bottom + 8
    if box.bottom > sh - 6:
        box.y = max(6, sh - box.h - 6)
    # Flat single-rim popup (no ornate corners / double border).
    _panel(client.screen, box, NAVY, GOLD, radius=8, width=1, ornate=False)
    help_r = pygame.Rect(box.x + 12, box.y + 14, box.w - 24, 30)
    logout_r = pygame.Rect(box.x + 12, box.y + 52, box.w - 24, 30)
    _panel(client.screen, help_r, NAVY_HI, GOLD_DIM, radius=5, width=1)
    _panel(client.screen, logout_r, (70, 32, 32), DANGER_RED, radius=5, width=1)
    help_l = _text(client, client.font_tiny, "Help", INK)
    logout_l = _text(client, client.font_tiny, "Logout", INK)
    client.screen.blit(help_l, (help_r.centerx - help_l.get_width() // 2,
                                help_r.centery - help_l.get_height() // 2))
    client.screen.blit(logout_l, (logout_r.centerx - logout_l.get_width() // 2,
                                  logout_r.centery - logout_l.get_height() // 2))
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
    ch = getattr(client, "hud_channel", None) or "world"
    if ch == "all":
        ch = "world"
        client.hud_channel = "world"
    idle = {
        "world": "World chat — Enter to talk",
        "guild": "Guild chat — members only",
        "party": "Party chat",
        "whisper": "Whisper — /w Name message",
    }.get(ch, "Press Enter to chat")
    prompt = (f"[{ch[:1].upper()}]> " + client.chat_text) if client.chat_typing else idle
    _blit(client, client.font_tiny, prompt[:70], (input_rect.x + 6, input_rect.y + 2), INK if client.chat_typing else MUTED)
    client.hud_rects["chat_input"] = input_rect


def _line_dict(line):
    if isinstance(line, dict):
        return line
    return {"text": str(line), "color": INK, "channel": "system"}


def _visible_lines(client):
    channel = client.hud_channel or "world"
    rows = []
    for raw in client.chat_log:
        line = _line_dict(raw)
        tagged = line.get("channel")
        # Untagged system/notice lines show on World; channel tabs stay private.
        if tagged == channel or (tagged is None and channel == "world"):
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
    auto_r = world.get("auto_pickup")
    if auto_r and auto_r.collidepoint(mx, my):
        client.toggle_auto_pickup()
        return True
    for key, rect in (world.get("utility") or {}).items():
        if rect.collidepoint(mx, my):
            _utility_click(client, key)
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
        client.net.send("SET_PK")
        return
    # Re-click the same focus panel (Quests, Guild, …) to return to inventory.
    if client.hud_focus == key:
        client.hud_focus = None
        client.hud_system = "inventory"
        return
    client.hud_focus = key
    client.hud_system = "inventory"
    if key == "guild":
        client.guild_tab = getattr(client, "guild_tab", None) or "home"
        client.guild_selected = None
        # Pull fresh roster / treasury / ranks (fixes stuck invite banner).
        try:
            client.net.send("GUILD_SYNC")
        except Exception:
            pass


def _action_click(client, key):
    if key == "eat":
        client.net.send("QUICK_CONSUME", kind="food")
        return
    client.set_combat_style(key)
    client.add_chat(f"Combat style: {key}.")


def _handle_chat_chrome_click(client, mx, my, rects):
    """Chat tabs / quick phrases / input — must work even while Guild focus is open."""
    for channel, rect in (rects.get("channels") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_channel = channel
            return True
    for phrase, rect in (rects.get("quick") or {}).items():
        if rect.collidepoint(mx, my):
            client.net.send("CHAT", text=phrase, channel="world")
            client.add_chat(f"You: {phrase}", color=CHANNEL_COLOR["world"], channel="world")
            return True
    chat_input = rects.get("chat_input")
    if chat_input and chat_input.collidepoint(mx, my):
        if hasattr(client, "_begin_chat_typing"):
            client._begin_chat_typing()
        else:
            client.chat_typing = True
        return True
    return False


def handle_sidebar_click(client, mx, my, button):
    ensure(client)
    rects = client.hud_rects or {}
    if getattr(client, "guild_prompt", None):
        handle_guild_prompt_click(client, mx, my)
        return True
    # Chat lives under the map; Guild focus must not swallow its clicks.
    if _handle_chat_chrome_click(client, mx, my, rects):
        return True
    # Menu Logout/Help must work even while Guild (or another focus) is open.
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
        # Click elsewhere closes the flyout but still processes the click below.
        client.hud_menu = False
    if client.hud_focus == "guild":
        for key, rect in (rects.get("guild_tabs") or {}).items():
            if rect.collidepoint(mx, my):
                client.guild_tab = key
                if key not in ("members", "board"):
                    client.guild_selected = None
                if key in ("members", "board"):
                    client.guild_scroll = 0
                return True
        for key, rect in (rects.get("guild_btns") or {}).items():
            if rect.collidepoint(mx, my):
                _guild_click(client, key)
                return True
        for name, rect in (rects.get("guild_members") or {}).items():
            if rect.collidepoint(mx, my):
                client.guild_selected = name
                client.guild_tab = "members"
                return True
        # Leave Guild only via system tabs / nav — never punch through to inventory.
        for key, rect in (rects.get("systems") or {}).items():
            if rect.collidepoint(mx, my):
                client.hud_system = key
                client.hud_focus = None
                return True
        for key, rect in (rects.get("utility") or {}).items():
            if rect.collidepoint(mx, my):
                _utility_click(client, key)
                return True
        for key, rect in (rects.get("nav") or {}).items():
            if rect.collidepoint(mx, my):
                _nav_click(client, key)
                return True
        if rects.get("header_logout") and rects["header_logout"].collidepoint(mx, my):
            client.logout()
            return True
        if rects.get("settings") and rects["settings"].collidepoint(mx, my):
            client.show_help = not client.show_help
            if client.show_help:
                client.help_scroll = 0
                client.show_equipment = False
            return True
        if rects.get("equipment") and rects["equipment"].collidepoint(mx, my):
            client.show_equipment = not client.show_equipment
            if client.show_equipment:
                client.show_help = False
            return True
        return True
    if rects.get("header_logout") and rects["header_logout"].collidepoint(mx, my):
        client.logout()
        return True
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
    quiver_equip = rects.get("quiver_equip") or {}
    if quiver_equip.get("rect") and quiver_equip["rect"].collidepoint(mx, my):
        client.net.send("EQUIP", slot_index=quiver_equip["slot"])
        client.add_chat("Equipping Arrow Quiver.")
        return
    quest_track = rects.get("quest_track") or {}
    if quest_track.get("rect") and quest_track["rect"].collidepoint(mx, my):
        npc = next((row for row in NPCS if row.get("id") == quest_track.get("npc_id")), None)
        if npc:
            # "Go" means "show me the way", not teleport: set a waypoint so
            # the edge arrow tracks it, and start walking if it's in view.
            import new_player_guide
            new_player_guide.set_waypoint(client, npc["x"], npc["y"], npc.get("name") or "Quest")
            client.walk_and_act(client.adjacent_goals(npc["x"], npc["y"]), {
                "type": "TALK", "npc_id": npc["id"],
            })
        else:
            # Kill-quest destination: walk to the camp centre via the same
            # pathing the travel modal uses, and mark it on the minimap.
            dest = rects.get("quest_track_dest") or {}
            if dest.get("x") is not None:
                import new_player_guide
                new_player_guide.set_waypoint(client, dest["x"], dest["y"], dest.get("label") or "Camp")
                client.travel_to_destination({"x": dest["x"], "y": dest["y"], "label": dest.get("label") or "Camp", "action": None})
        return
    if rects.get("skills") and rects["skills"].collidepoint(mx, my):
        client.toggle_skills_modal()
        return
    for key, rect in (rects.get("systems") or {}).items():
        if rect.collidepoint(mx, my):
            client.hud_system = key
            client.hud_focus = None
            return
    if client.hud_focus == "quests":
        for qid, rect in (rects.get("quest_rows") or {}).items():
            if rect.collidepoint(mx, my):
                if hasattr(client, "track_quest"):
                    client.track_quest(qid)
                else:
                    client.tracked_quest_id = None if getattr(client, "tracked_quest_id", None) == qid else qid
                return True
    # Inventory / crafting / gathering only when no left-nav focus panel is open.
    if not client.hud_focus:
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
        thumb = rects.get("inv_scroll_thumb")
        track = rects.get("inv_scroll_track")
        if thumb and thumb.collidepoint(mx, my):
            client.hud_inv_scroll_drag = {
                "y0": my,
                "scroll0": int(getattr(client, "hud_inv_scroll", 0) or 0),
            }
            return
        if track and track.collidepoint(mx, my):
            meta = getattr(client, "hud_inv_scroll_meta", None) or {}
            cap = int(meta.get("max_scroll") or getattr(client, "hud_inv_max_scroll", 0) or 0)
            if cap > 0 and track.h > 8:
                rel = (my - track.y) / float(track.h)
                client.hud_inv_scroll = max(0, min(cap, int(round(rel * cap))))
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
            client.net.send("CHAT", text=phrase, channel="world")
            client.add_chat(f"You: {phrase}", color=CHANNEL_COLOR["world"], channel="world")
            return
    chat_input = rects.get("chat_input")
    if chat_input and chat_input.collidepoint(mx, my):
        if hasattr(client, "_begin_chat_typing"):
            client._begin_chat_typing()
        else:
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
