"""Golden trail + edge arrow for new-player welcome and every active quest objective.

Welcome stages (Tamsin → Miriam) use WELCOME_STATE.show_path. Once a quest is
active, the same trail leads to that quest's destination (kill camp, collect
spot, find-NPC, or hand-in). Players should never wonder where to go.
"""
import math
import time

import pygame

from content import QUESTS, NPCS, TRAVEL_DESTINATIONS

GUIDE_ID = "warden_tamsin"
SARAH_NPC_ID = "innkeeper_sarah"      # after kit: food / HP before rats
SARAH_NPC_NAME = "Innkeeper Sarah"
NEXT_NPC_ID = "elder_miriam"          # then starter quest giver
NEXT_NPC_NAME = "Elder Miriam"

# Collect-quest item → travel destination id (when the quest has no guide_travel).
COLLECT_TRAVEL = {
    "lost_locket": "wishing_well",
    "rat_tail": "rats",
    "raw_shrimp": "lake",
    "cooked_trout": "inn_hearth",
    "cooked_lobster": "harbour_pier",
    "copper_ore": "copper_vein",
    "tin_ore": "copper_vein",
    "spider_silk": "dungeon_gate",
    "bones": "dungeon_gate",
    "big_bones": "dungeon_gate",
    "dragon_bones": "dungeon_gate",
}

# Collect item → monster type that drops it (circle a live kill target).
COLLECT_MONSTER = {
    "rat_tail": "giant_rat",
    "spider_silk": "spider",
    "bones": "skeleton",
    "big_bones": "giant",
    "dragon_bones": "dragon",
}

# Collect item → resource node type(s) to circle (mine / fish / chop).
COLLECT_RESOURCE = {
    "copper_ore": ("copper_rock",),
    "tin_ore": ("tin_rock",),
    "iron_ore": ("iron_rock",),
    "coal": ("coal_rock",),
    "mithril_ore": ("mithril_rock",),
    "adamantite_ore": ("adamantite_rock",),
    "raw_shrimp": ("fishing_spot_shrimp",),
    "raw_sardine": ("fishing_spot_sardine",),
    "raw_trout": ("fishing_spot_trout",),
    "raw_salmon": ("fishing_spot_salmon",),
    "raw_tuna": ("fishing_spot_tuna",),
    "raw_lobster": ("fishing_spot_lobster",),
    "raw_swordfish": ("fishing_spot_swordfish",),
    "logs": ("tree",),
    "oak_logs": ("oak_tree",),
    "willow_logs": ("willow_tree",),
    "maple_logs": ("maple_tree",),
    "yew_logs": ("yew_tree",),
    "magic_logs": ("magic_tree",),
}

# Void / depths aliases: quest target type → live monster types that count.
MONSTER_ALIASES = {
    "shade": ("shade", "rift_wraith"),
    "void_horror": ("void_horror", "nyxarath"),
    "giant": ("giant",),  # may be missing in Depths v2; trail falls back to Crypt
}
LINES = (
    "Click the ground to walk. Arrow keys / number pad step one tile.",
    "Follow the gold trail to Warden Tamsin for your Bronze kit.",
    "H = controls. Space = attack nearest monster.",
)
LINES_STAGE2 = (
    "Kit on — trail goes to Innkeeper Sarah (food/HP), then Elder Miriam for your first quest.",
)
LINES_DONE = (
    "Quest started — follow the gold trail. Sidebar Go re-sets the path.",
)
GOLD = (255, 214, 110)
GOLD_DEEP = (205, 140, 40)
SKIP_TEXT = "Tutorial skipped. Warden Tamsin stays by the crossroads if you still want your kit."
SKIP_TEXT_SARAH = "Tutorial skipped. Innkeeper Sarah (south) still teaches food/HP; Miriam has your first quest."
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
                      "owed": int(msg.get("owed") or 0), "eat_done": bool(msg.get("eat_done")),
                      "guide": dict(msg.get("guide") or {})}
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
    """tamsin → sarah (eat) → miriam until a quest is underway."""
    w = getattr(client, "welcome", None) or {}
    if not w.get("claimed"):
        return "tamsin", _guide_xy(client)
    if _quest_underway(client):
        return None, None
    if not w.get("eat_done"):
        return "sarah", _npc_xy(client, SARAH_NPC_ID)
    return "miriam", _npc_xy(client, NEXT_NPC_ID)


def guide_target_npc_id(client):
    """NPC id the golden trail currently wants you to talk to, or None."""
    if not visible(client):
        return None
    kind, _xy = _stage(client)
    if kind == "tamsin":
        return GUIDE_ID
    if kind == "sarah":
        return SARAH_NPC_ID
    if kind == "miriam":
        return NEXT_NPC_ID
    return None


def is_talk_prompt_npc(client, npc):
    """True when this NPC should show the Click me to talk highlight."""
    if not npc:
        return False
    tid = guide_target_npc_id(client)
    if tid and npc.get("id") == tid:
        return True
    # Quest hand-in / find-NPC / Go waypoint aimed at this tile.
    for key in ("quest_guide", "nav_waypoint"):
        wp = getattr(client, key, None)
        if not wp or len(wp) < 2:
            continue
        try:
            if int(npc.get("x")) == int(wp[0]) and int(npc.get("y")) == int(wp[1]):
                return True
        except (TypeError, ValueError):
            continue
    return False


def draw_talk_prompt(client, npc, cx, head_y):
    """Gold ring + 'Click me to talk' above a guide / waypoint NPC."""
    if not is_talk_prompt_npc(client, npc):
        return
    import math
    t = time.time()
    pulse = 0.55 + 0.45 * abs(math.sin(t * 3.5))
    # Ground ring under their feet
    rr = int(22 + 6 * pulse)
    ring = pygame.Surface((rr * 4, rr * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(ring, (*GOLD, int(90 + 100 * pulse)), (rr, rr // 2, rr * 2, rr), 3)
    client.screen.blit(ring, (cx - rr * 2, head_y + 36 - rr // 2))
    # Floating label
    label = "Click me to talk"
    font = client.font_small
    text = font.render(label, True, GOLD)
    pad_x, pad_y = 8, 4
    box = pygame.Rect(0, 0, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
    box.centerx = cx
    box.bottom = int(head_y - 8 - 4 * pulse)
    pygame.draw.rect(client.screen, (18, 22, 40), box, border_radius=6)
    pygame.draw.rect(client.screen, GOLD, box, 2, border_radius=6)
    client.screen.blit(text, (box.x + pad_x, box.y + pad_y))


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


def _travel_by_id(dest_id):
    return next((d for d in TRAVEL_DESTINATIONS if d.get("id") == dest_id), None)


def _npc_dest(npc_id, label=None):
    for npc in NPCS:
        if npc.get("id") == npc_id and npc.get("x") is not None:
            return int(npc["x"]), int(npc["y"]), label or npc.get("name") or "Quest"
    return None


def _all_other_quests_complete(client):
    quests = getattr(client, "quests", None) or {}
    others = [qid for qid in QUESTS if qid != "fairy_oath"]
    if not others:
        return True
    return all((quests.get(qid) or {}).get("status") == "complete" for qid in others)


def _tracked_qid(client):
    """Active quest for the gold trail — skips Royal Challenge until others are done."""
    quests = getattr(client, "quests", None) or {}

    def _ok(qid):
        if qid == "fairy_oath" and not _all_other_quests_complete(client):
            return False
        state = quests.get(qid) or {}
        return (state.get("status") or "") in ("active", "ready")

    qid = getattr(client, "tracked_quest_id", None)
    if qid and _ok(qid):
        return qid
    for qid, state in quests.items():
        if state and _ok(qid):
            return qid
    return None


def _player_xy(client):
    p = getattr(client, "player", None) or {}
    try:
        return int(p["x"]), int(p["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _monster_types(target):
    if not target:
        return ()
    return MONSTER_ALIASES.get(target) or (target,)


def _nearest_monster(client, types, label=None):
    """Closest living monster whose type is in types."""
    want = set(types or ())
    if not want:
        return None
    xy = _player_xy(client)
    if not xy:
        return None
    px, py = xy
    best, best_d = None, None
    for m in (getattr(client, "monsters", None) or {}).values():
        if not m or m.get("type") not in want:
            continue
        try:
            hp = m.get("hp")
            if hp is not None and int(hp) <= 0:
                continue
            mx, my = int(m["x"]), int(m["y"])
        except (KeyError, TypeError, ValueError):
            continue
        d = abs(mx - px) + abs(my - py)
        if best_d is None or d < best_d:
            best_d = d
            name = label or m.get("name") or next(iter(want))
            best = (mx, my, str(name)[:28])
    return best


def _nearest_resource(client, types, label=None):
    """Closest resource node matching types (copper_rock, fishing_spot_*, …)."""
    want = set(types or ())
    if not want:
        return None
    xy = _player_xy(client)
    if not xy:
        return None
    px, py = xy
    best, best_d = None, None
    for key, rtype in (getattr(client, "resources", None) or {}).items():
        if rtype not in want:
            continue
        try:
            rx, ry = map(int, str(key).split(","))
        except (TypeError, ValueError):
            continue
        d = abs(rx - px) + abs(ry - py)
        if best_d is None or d < best_d:
            best_d = d
            best = (rx, ry, str(label or rtype.replace("_", " ").title())[:28])
    return best


def _travel_dest(travel_id):
    place = _travel_by_id(travel_id)
    if not place:
        return None
    return int(place["x"]), int(place["y"]), place.get("label") or travel_id


def _collect_live_dest(client, item_id, need_remaining=True):
    """Circle a live drop-monster or resource for a collect item, else None."""
    if not item_id:
        return None
    mtype = COLLECT_MONSTER.get(item_id)
    if mtype:
        hit = _nearest_monster(client, _monster_types(mtype))
        if hit:
            return hit
    rtypes = COLLECT_RESOURCE.get(item_id)
    if rtypes:
        # Prefer ores still needed when multi-collect tracks progress externally.
        hit = _nearest_resource(client, rtypes)
        if hit:
            return hit
    return None


def quest_objective_dest(client, qid=None):
    """(x, y, label) for the current quest step, or None.

    Prefers a live target (monster to kill, ore to mine, NPC to talk to) so the
    gold ring circles the actual objective. Falls back to guide_travel / camp.
    """
    qid = qid or _tracked_qid(client)
    if not qid:
        return None
    qdef = QUESTS.get(qid) or {}
    state = (getattr(client, "quests", None) or {}).get(qid) or {}
    status = state.get("status") or "not_started"
    if status not in ("active", "ready"):
        return None

    # Explicit coords on the quest def.
    guide = qdef.get("guide") or {}
    if guide.get("x") is not None and guide.get("y") is not None:
        return int(guide["x"]), int(guide["y"]), guide.get("label") or qdef.get("name") or "Quest"

    if status == "ready":
        return _npc_dest(qdef.get("giver"), "Hand in")

    qtype = qdef.get("type")

    # Live targets first — circle the spider / ore / kill, not an empty camp pin.
    if qtype == "kill":
        live = _nearest_monster(client, _monster_types(qdef.get("target")))
        if live:
            return live
    elif qtype == "collect":
        live = _collect_live_dest(client, qdef.get("target"))
        if live:
            return live
    elif qtype == "collect_multi":
        targets = qdef.get("targets") or {}
        progress = state.get("progress") or {}
        # Prefer an item still short of its count.
        ordered = list(targets.items())
        ordered.sort(key=lambda kv: (int((progress.get(kv[0]) or 0)) >= int(kv[1]), kv[0]))
        for iid, need in ordered:
            have = int((progress.get(iid) or 0))
            if have >= int(need):
                continue
            live = _collect_live_dest(client, iid)
            if live:
                return live
        for iid in targets:
            live = _collect_live_dest(client, iid)
            if live:
                return live
    elif qtype == "find_npc":
        live = _npc_xy(client, qdef.get("target"))
        if live:
            npc = next((n for n in (getattr(client, "npcs", None) or [])
                        if n.get("id") == qdef.get("target")), None)
            return live[0], live[1], (npc or {}).get("name") or "Quest"

    # Travel id / camp fallback (entrance when the live target isn't loaded yet).
    travel_id = qdef.get("guide_travel") or guide.get("travel")
    if travel_id:
        place = _travel_dest(travel_id)
        if place:
            return place

    if qtype == "kill":
        camp = next((d for d in TRAVEL_DESTINATIONS
                     if d.get("kind") == "monster" and d.get("monster") == qdef.get("target")), None)
        if camp:
            return int(camp["x"]), int(camp["y"]), camp.get("label") or "Camp"
    elif qtype == "find_npc":
        return _npc_dest(qdef.get("target"))
    elif qtype == "collect":
        place = _travel_dest(COLLECT_TRAVEL.get(qdef.get("target")))
        if place:
            return place
    elif qtype == "collect_multi":
        for iid in (qdef.get("targets") or {}):
            place = _travel_dest(COLLECT_TRAVEL.get(iid))
            if place:
                return place
    elif qtype == "oath":
        # Royal Challenge is endgame — don't steal the gold trail until every
        # other quest is finished (journal still tracks progress meanwhile).
        if qid == "fairy_oath" and not _all_other_quests_complete(client):
            return None
        return _npc_dest(qdef.get("giver"))
    elif qtype in ("gift", "guild"):
        return _npc_dest(qdef.get("giver"))
    return None


def sync_quest_guide(client, announce=True):
    """Point the golden trail at the active quest objective (every quest)."""
    dest = quest_objective_dest(client)
    prev = getattr(client, "quest_guide", None)
    if dest is None:
        if prev is not None:
            client.quest_guide = None
            client._welcome_path = None
        return
    x, y, label = dest
    # Announce on camp/label change, not every time a live monster steps one tile.
    prev_label = prev[2] if prev else None
    same_place = prev and abs(prev[0] - x) <= 2 and abs(prev[1] - y) <= 2 and prev_label == label
    client.quest_guide = (x, y, label)
    client._welcome_path = None
    if announce and not same_place and prev_label != label:
        client.add_chat(
            f"Path set: {label}. Follow the golden trail (or the edge arrow).",
            color=GOLD, highlight=True,
        )


def active_trail_target(client):
    """(x, y, label) the breadcrumbs should lead to right now."""
    if not getattr(client, "player", None):
        return None
    if getattr(client, "state", None) != "GAME":
        return None
    outfitters = getattr(client, "outfitters", None)
    if outfitters is not None and getattr(outfitters, "active", False):
        return None
    # Welcome stages first while the kit trail is live (overworld only).
    if not getattr(client, "dungeon", None) and visible(client):
        kind, xy = _stage(client)
        if xy is not None:
            name = {
                "miriam": NEXT_NPC_NAME,
                "sarah": SARAH_NPC_NAME,
            }.get(kind, "Warden Tamsin")
            return xy[0], xy[1], name
    # Live quest objective every frame (circles the spider / ore, not a stale pin).
    live = quest_objective_dest(client)
    if live:
        return live
    qg = getattr(client, "quest_guide", None)
    if qg:
        return qg[0], qg[1], qg[2]
    # Keep trail on a manual Go waypoint too.
    wp = getattr(client, "nav_waypoint", None)
    if wp:
        return wp[0], wp[1], wp[2] or "Waypoint"
    return None


def trail(client):
    """Tiles from the player to the current guide target; recomputed only when either end changes."""
    target = active_trail_target(client)
    if target is None:
        return []
    gx, gy = int(target[0]), int(target[1])
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
    """Ground layer: glowing breadcrumbs toward welcome NPC or quest objective."""
    client._welcome_guide_screen = None
    target = active_trail_target(client)
    if target is None:
        return
    gx, gy = int(target[0]), int(target[1])
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
        # Bold pulsing ground circle on the live target (spider, ore, NPC…).
        ring = pygame.Surface((tile * 3, tile * 3), pygame.SRCALPHA)
        k = 0.5 + 0.5 * math.sin(now * 3.0)
        mid = tile * 3 // 2
        rr = int(tile * (0.62 + 0.14 * k))
        pygame.draw.ellipse(
            ring, (*GOLD, int(70 + 50 * k)),
            (mid - rr - 4, mid - rr // 2 - 2 + tile // 6, (rr + 4) * 2, rr + 6), 2,
        )
        pygame.draw.ellipse(
            ring, (*GOLD, int(160 + 90 * k)),
            (mid - rr, mid - rr // 2 + tile // 6, rr * 2, rr), 4,
        )
        client.screen.blit(ring, (hx - mid, hy - mid))
        label = str(target[2] or "Here")[:28]
        text = client.font_tiny.render(label, True, GOLD)
        client.screen.blit(text, (hx - text.get_width() // 2, hy - tile - 14))


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
    if kind == "sarah":
        return f"Next: {SARAH_NPC_NAME} — learn how food restores HP"
    if kind == "miriam":
        return f"Next: {NEXT_NPC_NAME} — accept your first quest"
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
        _edge_arrow(client, seen[0], seen[1], seen[3], {
            "miriam": NEXT_NPC_NAME,
            "sarah": SARAH_NPC_NAME,
        }.get(kind, "Warden Tamsin"))
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
    skip_msg = {"miriam": SKIP_TEXT2, "sarah": SKIP_TEXT_SARAH}.get(kind, SKIP_TEXT)
    client.add_chat(skip_msg, color=(255, 220, 150))


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

    Priority: active trail target (welcome / quest guide / Go waypoint).
    """
    target = active_trail_target(client)
    if not target:
        return None
    x, y, label = target
    qg = getattr(client, "quest_guide", None)
    if qg and qg[0] == x and qg[1] == y:
        colour = QUEST_COLOR
    elif visible(client):
        colour = GOLD
    else:
        colour = WAYPOINT_COLOR
    return x, y, label, colour


def set_waypoint(client, wx, wy, label):
    client.nav_waypoint = (int(wx), int(wy), str(label or "Waypoint")[:24])
    # Manual Go also becomes the quest trail tip so breadcrumbs appear.
    client.quest_guide = client.nav_waypoint
    client.add_chat(
        f"Path set: {client.nav_waypoint[2]}. Follow the golden trail (or the edge arrow).",
        color=WAYPOINT_COLOR,
    )
    client._welcome_path = None


def clear_waypoint(client):
    if getattr(client, "nav_waypoint", None) or getattr(client, "quest_guide", None):
        client.nav_waypoint = None
        client.quest_guide = None
        client._welcome_path = None
        client.add_chat("Path cleared.", color=WAYPOINT_COLOR)


def draw_waypoint(client, cam_x, cam_y, vis_w, vis_h, tile, area=None):
    """Edge arrow toward the active waypoint / quest turn-in, unless it is on screen.

    Called right after draw_trail, which already knows the camera and view size.
    Works in Crypt / Void instances too so Go can circle spiders and ores inside.
    """
    target = waypoint_target(client)
    if not target:
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
