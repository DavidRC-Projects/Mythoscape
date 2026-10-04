"""Void Sanctum v2 drawing, fog, banners and modals.

Drawers are copied from the design tool so the game does not import it.
Only used when the dungeon payload has v2 set.
"""
import math
import random
import time

import pygame

import procedural_sprites_finished as sprites
import prop_sprites
import rs_style as rs

FLOOR_PAL = {
    "entry": ((70, 60, 88), (62, 53, 80), (78, 68, 96), (56, 48, 72)),
    "gallery": ((84, 78, 92), (74, 68, 82), (92, 86, 100), (66, 60, 74)),
    "barracks": ((82, 70, 64), (72, 62, 56), (90, 78, 70), (64, 54, 50)),
    "crystal": ((52, 58, 92), (46, 50, 82), (60, 66, 104), (40, 44, 72)),
    "rift": ((44, 32, 58), (38, 28, 50), (52, 38, 66), (32, 24, 44)),
    "arena": ((30, 26, 38), (26, 22, 34), (36, 30, 46), (22, 18, 30)),
    "bridge": ((40, 36, 52), (36, 32, 48), (44, 40, 58), (34, 30, 44)),
}
WALL_PAL = {
    "entry": (46, 40, 60), "gallery": (58, 54, 66), "barracks": (56, 46, 42),
    "crystal": (36, 40, 70), "rift": (30, 22, 42), "arena": (22, 18, 30), "bridge": (22, 18, 30),
}
KEY_COL = {"A": (190, 120, 255), "B": (140, 150, 170), "C": (255, 120, 90)}
WHISPERS = (
    "The Circle of Selwyn opened the Rift.",
    "Stand on the runes. The wind obeys the throne.",
    "It is not a god. It is a hunger shaped like an eclipse.",
    "None pass the Amethyst Seal without the Warden's leave.",
)
DEPTH = {
    "entry": 0, "galleries": 1, "barracks": 2, "crystal": 3,
    "rift": 4, "whisper": 3, "bridge": 5, "arena": 6,
}


def attach(client, msg):
    d = client.dungeon
    flag = msg.get("v2")
    d["v2"] = True if flag is True else (flag or True)
    d["decor"] = dict(msg.get("decor") or {})
    d["zones"] = msg.get("zones") or []
    d["lore"] = msg.get("lore") or {}
    d["explored"] = set()
    d["banner_until"] = 0.0
    d["banner_text"] = ""
    d["last_zone"] = None
    d["whisper_at"] = time.time() + 60
    if msg.get("whispers"):
        d["whispers"] = list(msg["whispers"])
    if msg.get("banner_place"):
        d["banner_place"] = msg["banner_place"]
    if "depth_of" in msg:
        d["depth_of"] = msg.get("depth_of") or {}
    if msg.get("boss_type"):
        d["boss_type"] = msg["boss_type"]
        d["boss_label"] = msg.get("boss_label") or msg["boss_type"]
    if msg.get("secret_hints"):
        d["secret_hints"] = msg["secret_hints"]
    if msg.get("door_hints"):
        d["door_hints"] = msg["door_hints"]
    d["lore_modal"] = None
    d["warning_modal"] = False
    d["warning_seen"] = False
    d["wind_until"] = 0.0
    d["telegraphs"] = []
    ground = msg.get("ground_items") or {}
    if ground:
        client.ground_items = ground


def style_at(d, x, y):
    decor = (d.get("decor") or {}).get(f"{x},{y}", "")
    if decor in ("bridge", "anchor", "abyss"):
        return "bridge" if decor != "abyss" else "rift"
    for zone in d.get("zones") or []:
        x0, y0, x1, y1 = zone["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1 and zone["id"] != "whisper":
            return zone["style"]
    return "entry"


def zone_at(d, x, y):
    found = None
    for zone in d.get("zones") or []:
        x0, y0, x1, y1 = zone["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            if zone["id"] == "whisper" and x < 58:
                continue
            found = zone
            if zone["id"] != "whisper":
                return zone
    return found


def draw_tile(client, rect, tile_id, wx, wy, t):
    import world_map as wm
    d = client.dungeon
    decor = (d.get("decor") or {}).get(f"{wx},{wy}", "")
    style = style_at(d, wx, wy)
    if decor == "abyss" or (tile_id == wm.WALL and decor == "abyss"):
        draw_abyss(client.screen, rect, wx, wy, t)
        return
    if decor in ("bridge", "anchor"):
        draw_bridge(client.screen, rect, wx, wy, anchor=(decor == "anchor"), t=t)
        return
    if tile_id == wm.WALL:
        cracked = decor == "secret"
        draw_wall_top(client.screen, rect, wx, wy, style, cracked=cracked, t=t)
        if decor.startswith("seal"):
            open_ = decor.startswith("seal_open")
            key = decor.split(":")[-1]
            cx, cy = rect.centerx, rect.centery
            draw_seal(client.screen, cx, cy, rect.w, KEY_COL.get(key, (180, 140, 255)), open_, t)
            if not open_:
                mx, my = pygame.mouse.get_pos()
                if rect.collidepoint(mx, my):
                    label = _seal_label(client, decor)
                    if label:
                        client.blit_nameplate(label, rect.centerx, rect.y - 4, (230, 210, 255))
        if decor == "secret":
            mx, my = pygame.mouse.get_pos()
            if rect.collidepoint(mx, my):
                client.blit_nameplate("Loose bricks — click or walk into the wall", rect.centerx, rect.y - 4, (220, 210, 255))
        return
    draw_floor(client.screen, rect, wx, wy, style, t)
    _draw_prop(client, rect, decor, t)
    if client.player:
        px, py = client.player.get("x", 0), client.player.get("y", 0)
        if max(abs(wx - px), abs(wy - py)) <= 7:
            d.setdefault("explored", set()).add((wx, wy))
    explored = d.get("explored") or set()
    if (wx, wy) not in explored:
        fog = pygame.Surface(rect.size, pygame.SRCALPHA)
        fog.fill((6, 4, 12, 210))
        client.screen.blit(fog, rect.topleft)
    if decor == "secret":
        mx, my = pygame.mouse.get_pos()
        if rect.collidepoint(mx, my):
            client.blit_nameplate("Search Cracked wall", rect.centerx, rect.y - 4, (220, 210, 255))


def _draw_prop(client, rect, decor, t):
    cx, cy = rect.centerx, rect.centery
    tile = rect.w
    surf = client.screen
    if decor in ("chest", "chest_open"):
        if hasattr(sprites, "draw_chest"):
            sprites.draw_chest(surf, cx, cy, tile, t)
            if decor == "chest_open":
                # draw_chest has no open-lid argument; lift a lid above the body.
                pygame.draw.rect(
                    surf, (168, 124, 64),
                    (cx - tile // 5, cy - tile // 3, tile // 2, max(3, tile // 10)),
                )
        else:
            pygame.draw.rect(surf, (120, 84, 40), (cx - tile // 5, cy - tile // 6, tile // 2, tile // 3))
    elif decor == "lore":
        pygame.draw.rect(surf, (214, 196, 150), (cx - 8, cy - 5, 16, 9))
    elif decor in ("cache", "cache_open"):
        pygame.draw.rect(surf, (90, 70, 40) if decor == "cache_open" else (140, 100, 50), (cx - 10, cy - 6, 20, 12))
    elif decor == "shrine":
        prop_sprites.draw_prop(surf, "void_altar", cx, cy, tile)
    elif decor == "lever":
        pygame.draw.line(surf, (160, 50, 50), (cx, cy), (cx + 8, cy - 14), 3)
    elif decor == "warning":
        pygame.draw.polygon(surf, (80, 70, 90), [(cx - 8, cy + 6), (cx + 8, cy + 6), (cx, cy - 16)])
    elif decor == "pylon":
        lit = True
        for p in (client.dungeon.get("pylons") or []):
            if p["x"] == rect.x // max(1, tile) or True:
                pass
        pygame.draw.rect(surf, (70, 60, 90), (cx - 4, cy - 18, 8, 22))
        pygame.draw.circle(surf, (255, 210, 120), (cx, cy - 20), 4)
    elif decor == "rift":
        pygame.draw.ellipse(surf, (120, 40, 180), (cx - 12, cy - 6, 24, 12), 2)
    elif decor == "loot":
        pygame.draw.circle(surf, (230, 190, 70), (cx, cy), 4)
    elif decor == "pillar":
        pygame.draw.rect(surf, (70, 64, 84), (cx - 5, cy - 10, 10, 16))
    elif decor == "pedestal":
        pygame.draw.rect(surf, (60, 50, 70), (cx - 8, cy - 4, 16, 8))
        pygame.draw.circle(surf, (160, 170, 190), (cx, cy - 8), 4)


def draw_floor(surf, rect, x, y, style, t):
    pal = FLOOR_PAL.get(style, FLOOR_PAL["entry"])
    base = pal[int(sprites._seeded(x, y, 1) * 4) % 4]
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1))
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
    if style == "crystal" and sprites._seeded(x, y, 5) < 0.22:
        pygame.draw.circle(surf, (150, 170, 255), rect.center, max(2, rect.w // 7))
    elif style == "rift" and sprites._seeded(x, y, 5) < 0.3:
        pulse = int(80 + 40 * math.sin(t * 2 + x))
        pygame.draw.line(surf, (pulse, 40, 180), rect.topleft, rect.bottomright, 1)
    elif style == "arena":
        pygame.draw.rect(surf, (48, 38, 22), rect, 1)


def draw_wall_top(surf, rect, x, y, style, cracked=False, t=0.0):
    base = WALL_PAL.get(style, (40, 34, 52))
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, rs.shade(mid, -18), rect)
    pygame.draw.line(surf, hi, rect.topleft, (rect.right - 1, rect.top))
    if cracked:
        pygame.draw.rect(surf, rs.shade(mid, 18), rect.inflate(-3, -3))
        pygame.draw.line(surf, (255, 214, 120), (rect.centerx - 2, rect.top + 3), (rect.centerx - 6, rect.bottom - 3), 2)
        pygame.draw.line(surf, (255, 214, 120), (rect.centerx + 4, rect.top + 5), (rect.centerx - 1, rect.bottom - 4), 2)


def draw_abyss(surf, rect, x, y, t):
    pygame.draw.rect(surf, (8, 5, 14), rect)
    rnd = random.Random(x * 131 + y * 17)
    for _ in range(2):
        if rnd.random() < 0.5 and rect.w > 1 and rect.h > 1:
            surf.set_at((rect.x + rnd.randrange(rect.w), rect.y + rnd.randrange(rect.h)), (160, 120, 255))


def draw_bridge(surf, rect, x, y, anchor=False, t=0.0):
    draw_abyss(surf, rect, x, y, t)
    slab = rect.inflate(-max(2, rect.w // 6), -2)
    pygame.draw.rect(surf, (58, 52, 70), slab)
    if anchor:
        pygame.draw.circle(surf, (240, 200, 90), slab.center, max(2, rect.w // 5), 2)


def draw_seal(surf, cx, cy, tile, col, open_, t):
    sprites.draw_door(surf, cx, cy, tile, open_=open_, t=t)
    if open_:
        return
    pygame.draw.circle(surf, col, (int(cx), int(cy)), max(4, tile // 6), 2)


def queue_wall_faces(client, draw_list, cam_x, cam_y, vis_w, vis_h, t):
    import world_map as wm
    tile = client.TILE if hasattr(client, "TILE") else None
    # TILE is a closure in draw_map; the caller passes the live size via the rects.
    for sy in range(vis_h + 1):
        for sx in range(vis_w + 1):
            vx, vy = cam_x + sx, cam_y + sy
            wx, wy = client.view_to_world(vx, vy)
            if not (0 <= wy < len(client.tiles) and 0 <= wx < client.world_w):
                continue
            if client.tiles[wy][wx] != wm.WALL:
                continue
            decor = (client.dungeon.get("decor") or {}).get(f"{wx},{wy}", "")
            if decor == "abyss":
                continue
            marked = decor == "secret" or (decor or "").startswith("seal")
            if not marked and (wy + 1 >= len(client.tiles) or client.tiles[wy + 1][wx] == wm.WALL):
                continue
            style = style_at(client.dungeon, wx, wy)
            cracked = decor == "secret"

            def _face(sx=sx, sy=sy, style=style, cracked=cracked, decor=decor, wx=wx, wy=wy):
                tw = client.screen.get_width() and _tile(client)
                rect = pygame.Rect(sx * tw, sy * tw, tw, tw)
                draw_wall_face(client.screen, rect, style, cracked, t)
                label = _seal_label(client, decor)
                if label:
                    mx, my = pygame.mouse.get_pos()
                    if rect.collidepoint(mx, my):
                        client.blit_nameplate(label, rect.centerx, rect.y - 4, (230, 210, 255))

            draw_list.append(((sy + 1) * _tile(client), 2, _face))


def _seal_label(client, decor):
    if decor == "secret":
        return "Loose bricks — click or walk into the wall"
    if decor and decor.startswith("seal") and not decor.startswith("seal_open"):
        key = decor.split(":")[-1]
        return (client.dungeon.get("door_hints") or {}).get(key) or "Locked door — walk into it with the key"
    return ""


def _tile(client):
    import sys
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "TILE"):
        return main.TILE
    return 32


def draw_wall_face(surf, rect, style, cracked, t):
    base = WALL_PAL.get(style, (40, 34, 52))
    hi, mid, sh, _deep = rs.material(base)
    face = pygame.Rect(rect.x, rect.bottom, rect.w, rect.h // 2)
    pygame.draw.rect(surf, mid, face)
    pygame.draw.line(surf, sh, (face.x, face.centery), (face.right - 1, face.centery))
    pygame.draw.line(surf, hi, face.topleft, (face.right - 1, face.top))
    if cracked:
        pygame.draw.line(surf, (255, 214, 120), (face.centerx - 1, face.top), (face.centerx - 5, face.bottom - 2), 2)
        pygame.draw.line(surf, (255, 214, 120), (face.centerx + 4, face.top + 1), (face.centerx, face.bottom - 1), 2)


def handle_click(client, tx, ty):
    d = client.dungeon
    if d.get("lore_modal"):
        d["lore_modal"] = None
        return True
    if d.get("warning_modal"):
        d["warning_modal"] = False
        d["warning_seen"] = True
        return True
    decor = (d.get("decor") or {}).get(f"{tx},{ty}", "")
    interesting = decor.startswith("seal") or decor.startswith("sarcophagus") or decor in (
        "secret", "skull", "chest", "chest_open", "cache", "cache_open", "lore",
        "shrine", "lever", "pedestal", "warning", "sarcophagus",
    )
    if not interesting:
        return False
    goals = client.adjacent_goals(tx, ty)
    if client.tile_walkable(tx, ty):
        goals = set(goals) | {(tx, ty)}
    client.walk_and_act(goals, {"type": "DUNGEON_INTERACT", "x": tx, "y": ty})
    return True


def apply_tiles(client, msg):
    import world_map as wm
    for change in msg.get("changes") or []:
        x, y, tile = change
        if 0 <= y < len(client.tiles) and 0 <= x < len(client.tiles[y]):
            client.tiles[y][x] = tile
            if tile != wm.WALL:
                client.dungeon.setdefault("explored", set()).add((x, y))
    if "decor" in msg:
        client.dungeon["decor"] = msg["decor"]
    client._minimap_base = None


def on_state(client, dungeon_msg):
    if not client.dungeon or not client.dungeon.get("v2"):
        return
    for key in ("boss_phase", "pylons"):
        if key in dungeon_msg:
            client.dungeon[key] = dungeon_msg[key]


def on_wind(client, msg):
    if not client.dungeon:
        return
    if msg.get("warn"):
        client.dungeon["wind_until"] = time.time() + 2.0
        return
    client.dungeon["wind_until"] = 0.0
    if client.player and "x" in msg:
        client.player["x"] = msg["x"]
        client.player["y"] = msg["y"]
        client.player["hp"] = msg.get("hp", client.player.get("hp"))
        client.clear_walk()


def on_telegraph(client, msg):
    if not client.dungeon:
        return
    kind = msg.get("kind") or ""
    hold = 1.5 if kind == "hands" else 1.2 if kind in ("storm", "debris") else 2.2
    client.dungeon.setdefault("telegraphs", []).append({
        "tiles": msg.get("tiles") or [],
        "until": time.time() + hold,
        "kind": kind,
    })


def on_lore(client, msg):
    if client.dungeon:
        client.dungeon["lore_modal"] = {"title": msg.get("title", "Note"), "text": msg.get("text", "")}


def on_warning(client):
    if client.dungeon and not client.dungeon.get("warning_seen"):
        client.dungeon["warning_modal"] = True


def draw_overlay(client, t):
    d = client.dungeon
    if not d or not d.get("v2") or not client.player:
        return
    _note_explore(client)
    _banner(client)
    _whisper(client)
    _vignette(client)
    _wind(client, t)
    _telegraphs(client)
    _boss_bar(client)
    if d.get("lore_modal"):
        _parchment(client, d["lore_modal"]["title"], d["lore_modal"]["text"])
    if d.get("warning_modal"):
        _warning(client)


def _note_explore(client):
    d = client.dungeon
    px, py = int(client.player["x"]), int(client.player["y"])
    seen = d.setdefault("explored", set())
    before = len(seen)
    for dy in range(-7, 8):
        for dx in range(-7, 8):
            if max(abs(dx), abs(dy)) <= 7:
                seen.add((px + dx, py + dy))
    zone = zone_at(d, px, py)
    zid = zone["id"] if zone else None
    if zid and zid != d.get("last_zone"):
        d["last_zone"] = zid
        place = d.get("banner_place")
        if place:
            d["banner_text"] = f"{zone['name']} / {place} · {zone['band']}"
        else:
            d["banner_text"] = f"{zone['name']}  ·  {zone['band']}"
        d["banner_until"] = time.time() + 2.5
    if len(seen) != before:
        client._minimap_base = None


def _banner(client):
    d = client.dungeon
    if time.time() > d.get("banner_until", 0):
        return
    text = d.get("banner_text") or ""
    font = client.font_label
    img = font.render(text, True, (235, 220, 255))
    x = (900 - img.get_width()) // 2
    pygame.draw.rect(client.screen, (20, 12, 32), (x - 16, 70, img.get_width() + 32, img.get_height() + 12))
    client.screen.blit(img, (x, 76))


def _whisper(client):
    d = client.dungeon
    now = time.time()
    if now < d.get("whisper_at", 0):
        return
    d["whisper_at"] = now + 60
    lines = d.get("whispers") or WHISPERS
    client.add_chat(random.choice(lines), color=(180, 170, 140) if d.get("v2") == "depths" else (180, 150, 220))


def _vignette(client):
    zone = zone_at(client.dungeon, int(client.player["x"]), int(client.player["y"]))
    table = client.dungeon.get("depth_of")
    if table is None:
        table = DEPTH
    depth = table.get(zone["id"], 0) if zone else 0
    if depth <= 0:
        return
    veil = pygame.Surface((900, 640), pygame.SRCALPHA)
    veil.fill((8, 0, 16, 12 * depth))
    client.screen.blit(veil, (0, 0))


def _wind(client, t):
    if time.time() > client.dungeon.get("wind_until", 0):
        return
    streak = pygame.Surface((900, 640), pygame.SRCALPHA)
    for i in range(18):
        y = 40 + i * 34
        x = int((t * 220 + i * 50) % 980) - 40
        pygame.draw.line(streak, (160, 90, 220, 90), (x, y), (x + 70, y - 8), 2)
    client.screen.blit(streak, (0, 0))


def _telegraphs(client):
    now = time.time()
    live = []
    tile = _tile(client)
    for orb in client.dungeon.get("telegraphs") or []:
        if orb["until"] < now:
            continue
        live.append(orb)
        for x, y in orb["tiles"]:
            vx, vy = client.world_to_view(int(x), int(y))
            rect = pygame.Rect(vx * tile, vy * tile, tile, tile)
            kind = orb.get("kind") or ""
            col = {
                "hands": (120, 255, 150, 90),
                "storm": (230, 210, 140, 90),
                "debris": (140, 130, 120, 110),
            }.get(kind, (160, 60, 220, 90))
            mark = pygame.Surface((tile, tile), pygame.SRCALPHA)
            mark.fill(col)
            client.screen.blit(mark, rect.topleft)
    client.dungeon["telegraphs"] = live


def _boss_bar(client):
    phase = client.dungeon.get("boss_phase") or ""
    want = client.dungeon.get("boss_type") or "nyxarath"
    boss = None
    for m in client.monsters.values():
        if m.get("type") == want and m.get("alive"):
            boss = m
            break
    if not boss or not phase:
        return
    frac = boss["hp"] / max(1, boss.get("max_hp") or 1)
    bar = pygame.Rect(220, 8, 460, 18)
    fill = (120, 180, 110) if want == "morvath" else (160, 50, 180)
    pygame.draw.rect(client.screen, (20, 12, 24), bar)
    pygame.draw.rect(client.screen, fill, (bar.x, bar.y, int(bar.w * frac), bar.h))
    pygame.draw.rect(client.screen, (230, 190, 90), bar, 1)
    name = client.dungeon.get("boss_label") or "Nyxarath"
    label = client.font_tiny.render(f"{name}  ·  {phase}", True, (255, 230, 180))
    client.screen.blit(label, (bar.x + 8, bar.y + 2))


def _parchment(client, title, text):
    box = pygame.Rect(220, 160, 460, 220)
    pygame.draw.rect(client.screen, (214, 196, 150), box)
    pygame.draw.rect(client.screen, (90, 60, 30), box, 3)
    client.screen.blit(client.font_label.render(title, True, (60, 36, 16)), (box.x + 20, box.y + 16))
    words = text
    y = box.y + 52
    while words:
        line = words[:52]
        words = words[52:]
        client.screen.blit(client.font_small.render(line, True, (50, 32, 16)), (box.x + 20, y))
        y += 18
    client.screen.blit(client.font_tiny.render("Click to close", True, (90, 60, 30)), (box.x + 20, box.bottom - 24))


def _warning(client):
    box = pygame.Rect(240, 180, 420, 180)
    pygame.draw.rect(client.screen, (28, 18, 36), box)
    pygame.draw.rect(client.screen, (220, 170, 80), box, 2)
    lines = (
        "Beyond lies Nyxarath, the Hollow Eclipse.",
        "Recommended combat 100+.",
        "Cross only if you are ready.",
    )
    y = box.y + 20
    for line in lines:
        client.screen.blit(client.font_small.render(line, True, (255, 220, 160)), (box.x + 18, y))
        y += 22
    client.screen.blit(client.font_label.render("[ Click to continue ]", True, (255, 210, 90)), (box.x + 18, box.bottom - 40))


def minimap_hidden(client, wx, wy):
    if not client.dungeon or not client.dungeon.get("v2"):
        return False
    return (wx, wy) not in (client.dungeon.get("explored") or set())


def tint_and_halo(client, m, cx, cy, tile):
    from content import MONSTERS
    spec = MONSTERS.get(m.get("type")) or {}
    tint = spec.get("tint")
    if tint:
        glow = pygame.Surface((int(tile * 1.2), int(tile * 0.4)), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*tint, 70), glow.get_rect(), max(1, tile // 16))
        client.screen.blit(glow, (cx - glow.get_width() // 2, cy - glow.get_height() // 2))
    if m.get("type") == "nyxarath":
        pygame.draw.circle(client.screen, (230, 180, 70), (int(cx), int(cy - tile)), max(6, tile // 3), 2)
