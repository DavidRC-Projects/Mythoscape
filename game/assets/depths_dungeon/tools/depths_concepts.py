"""Build the concept PNGs for The Depths v2 crypt design (adapted from void_concepts.py)."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import depths_render as V  # noqa: E402
import pygame  # noqa: E402

OUT = V.OUT
F = V.F
pygame.display.set_mode((1, 1))


def panel(surf, rect, title=None, border=(200, 180, 130)):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((18, 16, 12, 228))
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=6)
    if title:
        surf.blit(F[16].render(title, True, (240, 228, 200)), (rect.x + 10, rect.y + 8))


def zone_banner(surf, cx, y, name, band):
    t1 = F[28].render(name, True, (245, 235, 210))
    t2 = F[14].render(band, True, (210, 200, 170))
    w = max(t1.get_width(), t2.get_width()) + 80
    r = pygame.Rect(0, 0, w, 70)
    r.midtop = (cx, y)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.fill((14, 12, 8, 205))
    surf.blit(s, r.topleft)
    pygame.draw.line(surf, (210, 190, 140), (r.x + 20, r.y + 4), (r.right - 20, r.y + 4), 2)
    pygame.draw.line(surf, (210, 190, 140), (r.x + 20, r.bottom - 4), (r.right - 20, r.bottom - 4), 2)
    surf.blit(t1, t1.get_rect(midtop=(cx, r.y + 8)))
    surf.blit(t2, t2.get_rect(midtop=(cx, r.y + 44)))


def boss_bar(surf, cx, y, name, frac, phase):
    w = 560
    r = pygame.Rect(0, 0, w, 46)
    r.midtop = (cx, y)
    panel(surf, r, None, (230, 190, 90))
    surf.blit(F[14].render(name, True, (255, 225, 150)), (r.x + 12, r.y + 4))
    ph = F[12].render(phase, True, (220, 230, 200))
    surf.blit(ph, (r.right - ph.get_width() - 12, r.y + 6))
    bar = pygame.Rect(r.x + 12, r.y + 26, w - 24, 12)
    pygame.draw.rect(surf, (20, 30, 20), bar)
    pygame.draw.rect(surf, (120, 200, 120), (bar.x, bar.y, int(bar.w * frac), bar.h))
    for f in (1 / 3, 2 / 3):
        pygame.draw.line(surf, (255, 225, 150), (bar.x + int(bar.w * f), bar.y - 2), (bar.x + int(bar.w * f), bar.bottom + 1), 2)
    pygame.draw.rect(surf, (230, 190, 90), bar, 1)



TXT = (240, 228, 200)
SUB = (214, 206, 186)


def before_map(tile):
    """Today's Depths interior, captured exactly as the server does."""
    import world_map
    import explore_dungeons
    grid = world_map.generate_world()
    explore_dungeons.capture_and_hide(grid)
    snap = explore_dungeons._SNAPSHOTS["depths"]
    tiles = snap["tiles"]
    h, w = len(tiles), len(tiles[0])
    s = pygame.Surface((w * tile, h * tile))
    import procedural_sprites_finished as sp
    for y in range(h):
        for x in range(w):
            r = pygame.Rect(x * tile, y * tile, tile, tile)
            t_ = tiles[y][x]
            if t_ in world_map.WALKABLE_TILES:
                sp.draw_floor(s, r, x, y, zone="dungeon")
            elif t_ in (world_map.IRON_ORE, world_map.COAL, world_map.MITHRIL_ORE, world_map.ADAMANTITE_ORE):
                pygame.draw.rect(s, (120, 100, 70), r)
            else:
                sp.draw_wall(s, r, "dungeon", x, y)
    return s, snap


def full_map():
    tile = 14
    m = V.render_region(0, 0, V.W - 1, V.H - 1, tile, markers=True,
                        opened_secrets=("hideyhole", "reliquary", "armoury"), opened_doors="")
    lw = 440
    img = pygame.Surface((m.get_width() + lw + 30, m.get_height() + 70))
    img.fill((16, 14, 10))
    img.blit(m, (10, 60))
    img.blit(F[28].render("The Depths v2: a crypt descent", True, TXT), (14, 12))
    ox, oy = 10, 60
    zc = {"chapel": (190, 200, 170), "ossuary": (235, 222, 190), "catacomb": (120, 200, 170), "tomb": (180, 190, 210),
          "mausoleum": (210, 190, 160), "wyrm": (230, 150, 90), "bridge": (240, 230, 190), "arena": (140, 255, 170)}
    pos = {"chapel": (24, 16), "ossuary": (6, 33), "catacombs": (9, 51), "tomb": (8, 66), "mausoleum": (14, 78) ,
           "wyrm": (1, 78), "bridge": (35, 85), "arena": (22, 105)}
    for zid, name, band, (x0, y0, x1, y1), style in V.MAP["zones"]:
        if zid == "stair":
            lab = pygame.transform.rotate(F[11].render("Sexton's Stair (shortcut)", True, (230, 200, 140)), 90)
            img.blit(lab, (ox + 64 * tile + 4, oy + 26 * tile))
            continue
        px, py = pos[zid]
        t = F[13].render(f"{name}  ·  {band}", True, zc[style])
        bx, by = ox + px * tile, oy + py * tile + 1
        if zid == "mausoleum":
            by -= 16
        if zid == "wyrm":
            by += 2
        bg = t.get_rect(topleft=(bx, by)).inflate(6, 2)
        pygame.draw.rect(img, (12, 10, 8), bg)
        img.blit(t, (bx, by))
    for sid, sp in V.MAP["secrets"].items():
        for (x0, y0, x1, y1) in sp["reveal"]:
            r = pygame.Rect(ox + x0 * tile, oy + y0 * tile, (x1 - x0 + 1) * tile, (y1 - y0 + 1) * tile)
            for i in range(0, r.w, 6):
                pygame.draw.line(img, (255, 210, 110), (r.x + i, r.y), (r.x + min(i + 3, r.w), r.y))
                pygame.draw.line(img, (255, 210, 110), (r.x + i, r.bottom - 1), (r.x + min(i + 3, r.w), r.bottom - 1))
            for i in range(0, r.h, 6):
                pygame.draw.line(img, (255, 210, 110), (r.x, r.y + i), (r.x, r.y + min(i + 3, r.h)))
                pygame.draw.line(img, (255, 210, 110), (r.right - 1, r.y + i), (r.right - 1, r.y + min(i + 3, r.h)))
    for txt, (lx, ly) in (("Sexton's Hidey-hole", (13, 13)), ("Drowned Reliquary", (1, 34)), ("Aldric's Armoury", (0, 54))):
        t = F[11].render(txt, True, (255, 215, 120))
        img.blit(t, (ox + lx * tile, oy + ly * tile))
    for ch, (x, y, key, nm) in V.MAP["doors"].items():
        V.draw_key_icon(img, ox + x * tile + 30, oy + y * tile + 7, 20, V.KEY_COL[ch])
        img.blit(F[11].render(f"Door {ch}", True, V.KEY_COL[ch]), (ox + x * tile + 46, oy + y * tile))
    L = pygame.Rect(m.get_width() + 20, 60, lw, m.get_height() - 10)
    panel(img, L, "Legend and route")
    y = L.y + 40
    rows = [
        ("marker", (90, 220, 90), "Monster, well below a lv-50 player"),
        ("marker", (240, 200, 60), "Monster, up to your level"),
        ("marker", (255, 140, 50), "Monster 1–8 levels above you"),
        ("marker", (255, 70, 60), "Monster 9+ levels above you"),
        ("boss", (255, 70, 60), "Mini-boss / boss (no respawn per visit)"),
        ("key", V.KEY_COL["A"], "A: Bone Key (Ossuary Keeper drop)"),
        ("key", V.KEY_COL["B"], "B: Tide Key (Drowned Reliquary, secret)"),
        ("key", V.KEY_COL["C"], "C: Knights' Seal (Sir Aldric drop)"),
        ("dash", (255, 210, 110), "Secret room (loose bricks / skull lever)"),
        ("Z", None, "Sarcophagus: search for loot, or an ambush"),
        ("c", None, "Chest (per-player, once per visit)"),
        ("l", None, "Lore note (9 notes: the Bone King's story)"),
        ("g", None, "Supply cache (food + potions)"),
        ("H", None, "Chapel shrine: checkpoint before the bridge"),
        ("v", None, "Lever: opens Sexton's Stair for good"),
        ("W", None, "Deep water (blocked) / shallow (walkable)"),
    ]
    for kind, col, txt in rows:
        cx, cy = L.x + 26, y + 10
        if kind == "marker":
            pygame.draw.circle(img, col, (cx, cy), 6)
        elif kind == "boss":
            pygame.draw.circle(img, col, (cx, cy), 8)
            pygame.draw.circle(img, (255, 230, 120), (cx, cy), 10, 1)
        elif kind == "key":
            V.draw_key_icon(img, cx + 4, cy, 22, col)
        elif kind == "dash":
            pygame.draw.rect(img, col, (cx - 8, cy - 7, 16, 14), 1)
        elif kind == "Z":
            V.draw_sarcophagus(img, cx, cy, 26)
        elif kind == "c":
            V.sprites.draw_chest(img, cx, cy + 6, 28)
        elif kind == "l":
            V.draw_scroll(img, cx, cy, 30)
        elif kind == "g":
            V.draw_cache(img, cx, cy + 4, 28)
        elif kind == "H":
            V.draw_shrine(img, cx, cy + 10, 24)
        elif kind == "v":
            V.draw_lever(img, cx, cy + 6, 28)
        elif kind == "W":
            V.draw_deep_water(img, pygame.Rect(cx - 12, cy - 8, 12, 16), 1, 1)
            V.draw_void_floor(img, pygame.Rect(cx, cy - 8, 12, 16), 1, 1, "catacomb")
            V.draw_shallow_water(img, pygame.Rect(cx, cy - 8, 12, 16), 1, 1)
        img.blit(F[12].render(txt, True, SUB), (L.x + 50, y + 3))
        y += 30
    y += 8
    route = [
        "Route (≈ 25–30 min first clear, combat 40–60):",
        "1  Ruined Chapel: goblins lv8, skeletons lv15. Fresh mortar",
        "    in the west wall hides the Sexton's Hidey-hole.",
        "2  Ossuary Halls: skeletons lv15, big skeletons lv30.",
        "    The Ossuary Keeper (lv34) drops the Bone Key (A).",
        "3  Flooded Catacombs: drowned dead lv36, spiders lv48.",
        "    Turn the odd skull → Drowned Reliquary → Tide Key (B).",
        "4  Tomb of the Knights: barrow knights lv44, 12 sarcophagi",
        "    (loot or ambush). Sir Aldric (lv52) → Knights' Seal (C).",
        "5  Collapsed Mausoleum: shades lv55, ghouls lv62.",
        "    Shrine, warning stone, lever → Sexton's Stair.",
        "    Optional: Wyrm Ossuary, today's Adamant Dragon (lv78).",
        "6  The Bone Bridge: grasping hands root you; watch",
        "    for glowing cracks and keep moving.",
        "7  Throne of Bones: Morvath, the Bone King (lv70), 3 phases.",
    ]
    for line in route:
        img.blit(F[12].render(line, True, TXT if line.startswith("Route") else SUB), (L.x + 14, y))
        y += 19
    b, snap = before_map(6)
    y += 12
    img.blit(F[13].render("Before: today's Depths (goblins → dragon, ore rooms)", True, (255, 200, 160)), (L.x + 14, y))
    y += 20
    avail = L.bottom - 8 - y
    sc = min((lw - 28) / b.get_width(), avail / b.get_height())
    bb = pygame.transform.smoothscale(b, (int(b.get_width() * sc), int(b.get_height() * sc)))
    img.blit(bb, (L.x + 14, y))
    pygame.image.save(img, os.path.join(OUT, "depths_map_full.png"))


def bridge_closeup():
    tile = 32
    x0, y0, x1, y1 = 13, 70, 53, 105
    t = 1.1
    m = V.render_region(x0, y0, x1, y1, tile, t=t, opened_doors="ABC", player=(33, 84))
    for hy in (87, 89):   # two hand tiles telegraphed ahead of the player
        r = pygame.Rect((33 - x0) * tile, (hy - y0) * tile, tile, tile)
        V.draw_grasping_hands(m, r, t)
    V.nameplate(m, "Bones crack beneath you: grasping hands!", (33 - x0) * tile + 190, (88 - y0) * tile, (160, 255, 180), F[14])
    V.nameplate(m, "Chapel shrine (checkpoint)", (33 - x0) * tile + 16, (76 - y0) * tile - 46, (255, 230, 160), F[12])
    zone_banner(m, m.get_width() // 2, 8, "The Bone Bridge", "Grasping hands · The Bone King waits below")
    boss_bar(m, m.get_width() // 2, m.get_height() - 62, "Morvath, the Bone King  ·  lv 70", 0.52, "Phase 2 of 3: Raise the Dead")
    pr = pygame.Rect(22, 150, 340, 118)
    panel(m, pr, "The Throne of Bones lies below", (230, 190, 90))
    for i, line in enumerate(["Morvath has not left his throne in 300 years.",
                              "Recommended: combat 50+, food, prayer-free melee.",
                              "[ Cross ]     [ Not yet ]"]):
        m.blit(F[12].render(line, True, SUB), (pr.x + 12, pr.y + 38 + i * 24))
    pygame.image.save(m, os.path.join(OUT, "depths_bridge_boss_closeup.png"))


def secret_before_after():
    tile = 40
    x0, y0, x1, y1 = 1, 35, 17, 47
    before = V.render_region(x0, y0, x1, y1, tile, t=0.6, show_mons=False, player=(9, 39))
    after = V.render_region(x0, y0, x1, y1, tile, t=0.6, show_mons=False, opened_secrets=("reliquary",), player=(6, 39))
    zoom = pygame.transform.scale(before.subsurface(pygame.Rect((6 - x0) * tile, (38 - y0) * tile, tile * 3, tile * 3)).copy(), (tile * 5, tile * 5))
    wx, wy = (7 - x0) * tile + tile // 2, (39 - y0) * tile
    tip = pygame.Rect(wx - 20, wy - 70, 340, 50)
    panel(before, tip, None, (200, 180, 120))
    before.blit(F[13].render("Turn  Odd skull", True, (255, 230, 150)), (tip.x + 10, tip.y + 6))
    before.blit(F[11].render("One skull faces the wrong way. Its eyes catch the light.", True, SUB), (tip.x + 10, tip.y + 28))
    zx, zy = before.get_width() - tile * 5 - 16, before.get_height() - tile * 5 - 16
    before.blit(zoom, (zx, zy))
    pygame.draw.rect(before, (255, 210, 110), (zx, zy, tile * 5, tile * 5), 2)
    before.blit(F[12].render("zoom: the skull niche", True, (255, 210, 110)), (zx + 6, zy - 18))
    chat = pygame.Rect(8, after.get_height() - 44, 560, 36)
    panel(after, chat, None, (200, 180, 120))
    after.blit(F[12].render("Click. The niche swings inward: the Drowned Reliquary!", True, (255, 230, 150)), (chat.x + 10, chat.y + 10))
    W_, H_ = before.get_width(), before.get_height()
    img = pygame.Surface((W_ * 2 + 30, H_ + 50))
    img.fill((16, 14, 10))
    img.blit(F[18].render("BEFORE: skull-lever hint in the catacomb wall", True, TXT), (10, 12))
    img.blit(F[18].render("AFTER: Drowned Reliquary (Tide Key, chest, confession)", True, TXT), (W_ + 30, 12))
    img.blit(before, (10, 44))
    img.blit(after, (W_ + 20, 44))
    pygame.image.save(img, os.path.join(OUT, "depths_secret_wall_before_after.png"))


KEY_NAMES = {"A": "Bone Key", "B": "Tide Key", "C": "Knights' Seal"}
KEY_SRC = {"A": "Drop: Ossuary Keeper (100%)", "B": "Secret: Drowned Reliquary pedestal", "C": "Drop: Sir Aldric (100%)"}


def door_and_key():
    tile = 40
    x0, y0, x1, y1 = 25, 28, 41, 39
    locked = V.render_region(x0, y0, x1, y1, tile, t=0.9, show_mons=False, player=(33, 32))
    opened = V.render_region(x0, y0, x1, y1, tile, t=0.9, show_mons=False, player=(33, 36), opened_doors="A")
    tip = pygame.Rect(20, 16, 460, 56)
    panel(locked, tip, None, V.KEY_COL["A"])
    locked.blit(F[13].render("Unlock  Bone Gate", True, (240, 225, 190)), (tip.x + 10, tip.y + 6))
    locked.blit(F[11].render("Locked. A Bone Key fits here; the Ossuary Keeper carries one.", True, SUB), (tip.x + 10, tip.y + 30))
    chat = pygame.Rect(8, opened.get_height() - 44, 560, 36)
    panel(opened, chat, None, V.KEY_COL["A"])
    opened.blit(F[12].render("The Bone Key crumbles to dust; the gate opens (for you only).", True, (240, 225, 190)), (chat.x + 10, chat.y + 10))
    W_, H_ = locked.get_width(), locked.get_height()
    kw = 370
    img = pygame.Surface((W_ * 2 + kw + 40, H_ + 50))
    img.fill((16, 14, 10))
    img.blit(F[18].render("Locked gate (door A)", True, TXT), (10, 12))
    img.blit(F[18].render("Unlocked with the key", True, TXT), (W_ + 20, 12))
    img.blit(locked, (10, 44))
    img.blit(opened, (W_ + 20, 44))
    K = pygame.Rect(W_ * 2 + 30, 44, kw, H_)
    panel(img, K, "Crypt keys (bound to the visit)")
    y = K.y + 46
    for ch in "ABC":
        nm = V.MAP["doors"][ch][3]
        slot = pygame.Rect(K.x + 14, y, 64, 64)
        pygame.draw.rect(img, (40, 34, 30), slot)
        pygame.draw.rect(img, (90, 80, 60), slot, 2)
        V.draw_key_icon(img, slot.centerx + 2, slot.centery, 44, V.KEY_COL[ch])
        img.blit(F[14].render(KEY_NAMES[ch], True, V.KEY_COL[ch]), (slot.right + 12, y + 6))
        img.blit(F[11].render(KEY_SRC[ch], True, SUB), (slot.right + 12, y + 28))
        img.blit(F[11].render(f"Opens the {nm} (door {ch})", True, (190, 182, 160)), (slot.right + 12, y + 44))
        y += 86
    img.blit(F[12].render("Inventory scale (36 px):", True, SUB), (K.x + 14, y + 4))
    for i, ch in enumerate("ABC"):
        slot = pygame.Rect(K.x + 14 + i * 44, y + 26, 36, 36)
        pygame.draw.rect(img, (40, 34, 30), slot)
        V.draw_key_icon(img, slot.centerx + 1, slot.centery, 26, V.KEY_COL[ch])
    pygame.image.save(img, os.path.join(OUT, "depths_locked_door_and_key.png"))


def sarcophagus_search():
    tile = 40
    x0, y0, x1, y1 = 13, 53, 23, 60
    sx, sy = 17, 56
    panels = []
    for state, title in (("closed", "1  Search the sarcophagus"), ("loot", "2a  Loot (55%)"), ("ambush", "2b  Ambush! (30%)")):
        V.SARC_STATE.clear()
        V.SARC_STATE[(sx, sy)] = state
        s = V.render_region(x0, y0, x1, y1, tile, t=0.8, show_mons=False, player=(sx, sy + 2))
        if state == "closed":
            tip = pygame.Rect(40, 20, 380, 50)
            panel(s, tip, None, (200, 180, 120))
            s.blit(F[13].render("Search  Knight's sarcophagus", True, (255, 230, 150)), (tip.x + 10, tip.y + 6))
            s.blit(F[11].render("The lid is carved with a sleeping knight. It isn't sealed.", True, SUB), (tip.x + 10, tip.y + 28))
        elif state == "loot":
            chat = pygame.Rect(8, s.get_height() - 44, 480, 36)
            panel(s, chat, None, (200, 180, 120))
            s.blit(F[12].render("You find 64 coins and a Steel longsword.", True, (255, 230, 150)), (chat.x + 10, chat.y + 10))
        else:
            for mt, mx, my in (("skeleton", sx - 1, sy + 1), ("barrow_knight", sx + 1, sy + 1)):
                cx, cy = (mx - x0) * tile + tile // 2, (my - y0) * tile + int(tile * 0.8)
                V.draw_mon(s, mt, cx, cy, tile, 0.8, facing=1 if mx < sx else -1)
                lvl = 40 if mt == "skeleton" else V.LEVEL[mt]
                V.badge(s, str(lvl), cx, cy - int(tile * 1.8), V.threat_col(lvl), F[13])
            chat = pygame.Rect(8, s.get_height() - 44, 480, 36)
            panel(s, chat, None, (140, 255, 170))
            s.blit(F[12].render("The dead stir! A barrow knight and a risen squire (lv40) rise.", True, (170, 255, 190)), (chat.x + 10, chat.y + 10))
        panels.append((title, s))
    V.SARC_STATE.clear()
    W_, H_ = panels[0][1].get_size()
    img = pygame.Surface((W_ * 3 + 40, H_ + 50))
    img.fill((16, 14, 10))
    for i, (title, s) in enumerate(panels):
        img.blit(F[18].render(title, True, TXT), (10 + i * (W_ + 10), 12))
        img.blit(s, (10 + i * (W_ + 10), 44))
    pygame.image.save(img, os.path.join(OUT, "depths_sarcophagus_search_ambush.png"))


def zone_strip():
    tile = 40
    crops = [("Ruined Chapel · lv 8–15", (23, 3, 43, 15), (33, 5)),
             ("Ossuary Halls · lv 15–34", (39, 16, 57, 29), None),
             ("Flooded Catacombs · lv 36–48", (8, 36, 34, 50), None),
             ("Tomb of the Knights · lv 44–52", (30, 52, 52, 66), None),
             ("Collapsed Mausoleum · lv 55–62", (28, 67, 50, 79), (33, 75))]
    imgs = []
    for title, (x0, y0, x1, y1), pl in crops:
        s = V.render_region(x0, y0, x1, y1, tile, t=0.7, opened_doors="ABC", player=pl)
        if title.startswith("Ruined"):
            zone_banner(s, s.get_width() // 2, 90, "Ruined Chapel", "The Depths · Lv 8–15")
        sc = 560 / s.get_width()
        s = pygame.transform.smoothscale(s, (560, int(s.get_height() * sc)))
        imgs.append((title, s))
    fog = V.render_region(5, 2, 59, 34, 14, t=0.7, markers=True, fog=(33, 22, 9), opened_doors="")
    fsc = 560 / fog.get_width()
    fog = pygame.transform.smoothscale(fog, (560, int(fog.get_height() * fsc)))
    imgs.append(("Fog of war (explored radius; minimap follows)", fog))
    cols = 2
    rows = (len(imgs) + 1) // 2
    hmax = max(i[1].get_height() for i in imgs)
    img = pygame.Surface((cols * 580 + 10, rows * (hmax + 36) + 10))
    img.fill((16, 14, 10))
    for i, (title, s) in enumerate(imgs):
        x = 10 + (i % cols) * 580
        y = 10 + (i // cols) * (hmax + 36)
        img.blit(F[16].render(title, True, TXT), (x, y))
        img.blit(s, (x, y + 26))
    pygame.image.save(img, os.path.join(OUT, "depths_zones_gamescale.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    msgs, checks = V.validate()
    print("spawn issues:", msgs, "checks:", all(checks.values()))
    full_map()
    bridge_closeup()
    secret_before_after()
    door_and_key()
    sarcophagus_search()
    zone_strip()
    print("done")
