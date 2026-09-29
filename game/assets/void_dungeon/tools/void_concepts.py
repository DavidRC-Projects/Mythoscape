"""Build the concept PNGs for the Void Sanctum v2 design (see void_render.py)."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import void_render as V  # noqa: E402
import pygame  # noqa: E402

OUT = V.OUT
F = V.F
pygame.display.set_mode((1, 1))


def panel(surf, rect, title=None, border=(180, 120, 255)):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((16, 10, 24, 225))
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=6)
    if title:
        surf.blit(F[16].render(title, True, (235, 215, 255)), (rect.x + 10, rect.y + 8))


def zone_banner(surf, cx, y, name, band):
    t1 = F[28].render(name, True, (240, 220, 255))
    t2 = F[14].render(band, True, (200, 170, 240))
    w = max(t1.get_width(), t2.get_width()) + 80
    r = pygame.Rect(0, 0, w, 70)
    r.midtop = (cx, y)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.fill((10, 4, 18, 200))
    surf.blit(s, r.topleft)
    pygame.draw.line(surf, (200, 160, 255), (r.x + 20, r.y + 4), (r.right - 20, r.y + 4), 2)
    pygame.draw.line(surf, (200, 160, 255), (r.x + 20, r.bottom - 4), (r.right - 20, r.bottom - 4), 2)
    surf.blit(t1, t1.get_rect(midtop=(cx, r.y + 8)))
    surf.blit(t2, t2.get_rect(midtop=(cx, r.y + 44)))


def boss_bar(surf, cx, y, name, frac, phase):
    w = 560
    r = pygame.Rect(0, 0, w, 46)
    r.midtop = (cx, y)
    panel(surf, r, None, (230, 190, 90))
    surf.blit(F[14].render(name, True, (255, 225, 150)), (r.x + 12, r.y + 4))
    ph = F[12].render(phase, True, (220, 200, 255))
    surf.blit(ph, (r.right - ph.get_width() - 12, r.y + 6))
    bar = pygame.Rect(r.x + 12, r.y + 26, w - 24, 12)
    pygame.draw.rect(surf, (40, 10, 20), bar)
    pygame.draw.rect(surf, (170, 40, 200), (bar.x, bar.y, int(bar.w * frac), bar.h))
    for f in (1 / 3, 2 / 3):
        pygame.draw.line(surf, (255, 225, 150), (bar.x + int(bar.w * f), bar.y - 2), (bar.x + int(bar.w * f), bar.bottom + 1), 2)
    pygame.draw.rect(surf, (230, 190, 90), bar, 1)


def before_map(tile):
    """Today's Void Sanctum interior (captured exactly as the server does)."""
    import world_map
    import explore_dungeons
    grid = world_map.generate_world()
    explore_dungeons.capture_and_hide(grid)
    snap = explore_dungeons._SNAPSHOTS["sanctum"]
    tiles = snap["tiles"]
    h, w = len(tiles), len(tiles[0])
    s = pygame.Surface((w * tile, h * tile))
    import procedural_sprites_finished as sp
    for y in range(h):
        for x in range(w):
            r = pygame.Rect(x * tile, y * tile, tile, tile)
            if tiles[y][x] in world_map.WALKABLE_TILES:
                sp.draw_floor(s, r, x, y, zone="dungeon")
            else:
                sp.draw_wall(s, r, "dungeon", x, y)
    return s, snap


def full_map():
    tile = 14
    m = V.render_region(0, 0, V.W - 1, V.H - 1, tile, markers=True,
                        opened_secrets=("reliquary", "quartermaster", "starwell"), opened_doors="")
    lw = 430
    img = pygame.Surface((m.get_width() + lw + 30, m.get_height() + 70))
    img.fill((14, 10, 20))
    img.blit(m, (10, 60))
    img.blit(F[28].render("Void Sanctum v2: the descent", True, (235, 215, 255)), (14, 12))
    ox, oy = 10, 60
    # zone outlines + labels
    zc = {"entry": (150, 120, 220), "gallery": (190, 190, 210), "barracks": (210, 150, 110), "crystal": (120, 150, 255),
          "rift": (200, 90, 255), "bridge": (255, 210, 110), "arena": (255, 200, 90)}
    for zid, name, band, (x0, y0, x1, y1), style in V.MAP["zones"]:
        if zid == "whisper":
            lab = F[11].render("Whispering Passage (shortcut)", True, (200, 160, 255))
            lab = pygame.transform.rotate(lab, 90)
            img.blit(lab, (ox + 62 * tile + 4, oy + 22 * tile))
            continue
        col = zc[style]
        t = F[13].render(f"{name}  ·  {band}", True, col)
        bx, by = ox + x0 * tile + 4, oy + y0 * tile + 2
        if zid == "entry":
            bx, by = ox + 24 * tile, oy + 14 * tile + 1
        if zid == "galleries":
            by = oy + 31 * tile + 1
        if zid == "barracks":
            bx, by = ox + 11 * tile, oy + 47 * tile + 1
        if zid == "crystal":
            bx, by = ox + 5 * tile, oy + 60 * tile + 1
        if zid == "rift":
            bx, by = ox + 15 * tile, oy + 72 * tile - 16
        if zid == "bridge":
            bx, by = ox + 34 * tile, oy + 78 * tile
        if zid == "arena":
            bx, by = ox + 21 * tile, oy + 98 * tile + 1
        bg = t.get_rect(topleft=(bx, by)).inflate(6, 2)
        pygame.draw.rect(img, (10, 6, 16), bg)
        img.blit(t, (bx, by))
    # secret room outlines (dashed gold)
    for sid, sp in V.MAP["secrets"].items():
        for (x0, y0, x1, y1) in sp["reveal"]:
            r = pygame.Rect(ox + x0 * tile, oy + y0 * tile, (x1 - x0 + 1) * tile, (y1 - y0 + 1) * tile)
            for i in range(0, r.w, 6):
                pygame.draw.line(img, (255, 210, 110), (r.x + i, r.y), (r.x + min(i + 3, r.w), r.y))
                pygame.draw.line(img, (255, 210, 110), (r.x + i, r.bottom - 1), (r.x + min(i + 3, r.w), r.bottom - 1))
            for i in range(0, r.h, 6):
                pygame.draw.line(img, (255, 210, 110), (r.x, r.y + i), (r.x, r.y + min(i + 3, r.h)))
                pygame.draw.line(img, (255, 210, 110), (r.right - 1, r.y + i), (r.right - 1, r.y + min(i + 3, r.h)))
    labels = {"reliquary": ("Hidden Reliquary", (13, 12)), "quartermaster": ("QM Cache", (2, 46)),
              "starwell": ("Starwell", (43, 65))}
    for sid, (txt, (lx, ly)) in labels.items():
        t = F[11].render(txt, True, (255, 215, 120))
        img.blit(t, (ox + lx * tile, oy + ly * tile))
    # door / key callouts
    for ch, (x, y, key, nm) in V.MAP["doors"].items():
        V.draw_key_icon(img, ox + x * tile + 30, oy + y * tile + 7, 20, V.KEY_COL[ch])
        t = F[11].render(f"Door {ch}", True, V.KEY_COL[ch])
        img.blit(t, (ox + x * tile + 46, oy + y * tile))
    # legend
    L = pygame.Rect(m.get_width() + 20, 60, lw, m.get_height() - 10)
    panel(img, L, "Legend and route")
    y = L.y + 40
    rows = [
        ("marker", (90, 220, 90), "Monster, level below you (for a lv-90 player)"),
        ("marker", (240, 200, 60), "Monster, level up to your own"),
        ("marker", (255, 140, 50), "Monster 1–8 levels above you"),
        ("marker", (255, 70, 60), "Monster 9+ levels above you"),
        ("boss", (255, 70, 60), "Mini-boss / boss (no respawn per visit)"),
        ("key", V.KEY_COL["A"], "A: Amethyst Key (Gallery Warden drop)"),
        ("key", V.KEY_COL["B"], "B: Obsidian Key (QM Cache, secret)"),
        ("key", V.KEY_COL["C"], "C: Rift Sigil (Knight-Captain Vorn drop)"),
        ("dash", (255, 210, 110), "Secret room (cracked wall; search it)"),
        ("c", None, "Chest (per-player loot, once per visit)"),
        ("l", None, "Lore note (10 notes tell the story)"),
        ("g", None, "Supply cache (food + potions)"),
        ("$", None, "Ground loot pile"),
        ("H", None, "Healing shrine / checkpoint"),
        ("v", None, "Lever: opens the shortcut gate for good"),
        ("a", None, "Bridge rune anchor (safe from void wind)"),
        ("o", None, "Eclipse pylon (light-safe in phase 3)"),
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
        elif kind == "c":
            V.sprites.draw_chest(img, cx, cy + 6, 28)
        elif kind == "l":
            V.draw_scroll(img, cx, cy, 30)
        elif kind == "g":
            V.draw_cache(img, cx, cy + 4, 28)
        elif kind == "$":
            V.draw_loot_pile(img, cx, cy, 32)
        elif kind == "H":
            pygame.draw.circle(img, (120, 255, 170), (cx, cy), 7)
        elif kind == "v":
            V.draw_lever(img, cx, cy + 6, 28)
        elif kind == "a":
            V.draw_bridge(img, pygame.Rect(cx - 9, cy - 9, 18, 18), 1, 1, anchor=True)
        elif kind == "o":
            V.draw_pylon(img, cx, cy + 10, 22)
        img.blit(F[12].render(txt, True, (225, 220, 235)), (L.x + 50, y + 3))
        y += 30
    y += 10
    route = [
        "Route (≈ 25–35 min first clear):",
        "1  Entry Hall: shades lv55. Crack in the west wall.",
        "2  Galleries: ghouls lv62. Gallery Warden drops Key A.",
        "3  Barracks: imps lv70, colossi lv78. Secret QM",
        "    Cache on the west wall holds Key B.",
        "4  Crystal Depths: crawlers lv82, knights lv88.",
        "    Knight-Captain Vorn (lv92) drops the Rift Sigil (C).",
        "5  Rift Edge: wraiths lv91, horrors lv95. Shrine,",
        "    warning stone, lever → shortcut to the Entry Hall.",
        "6  The Narrow Way: 1-tile bridge, void wind every",
        "    10 s; stand on rune anchors.",
        "7  Eclipse Throne: Nyxarath lv110, 3 phases.",
        "Re-runs: shortcut gate → Rift Edge directly.",
    ]
    for line in route:
        img.blit(F[12].render(line, True, (230, 215, 255) if line.startswith("Route") or line.startswith("Re-") else (205, 200, 215)), (L.x + 14, y))
        y += 19
    # inset: today's dungeon at the same scale
    b, snap = before_map(tile // 2 + 2)
    y += 16
    img.blit(F[13].render("Before (same tile scale ÷ 1.75): one open room", True, (255, 200, 160)), (L.x + 14, y))
    y += 20
    sc = min(1.0, (lw - 28) / b.get_width())
    bb = pygame.transform.smoothscale(b, (int(b.get_width() * sc), int(b.get_height() * sc)))
    if y + bb.get_height() < L.bottom - 6:
        img.blit(bb, (L.x + 14, y))
    pygame.image.save(img, os.path.join(OUT, "void_map_full.png"))
    return img


def bridge_closeup():
    tile = 32
    x0, y0, x1, y1 = 14, 64, 50, 98
    t = 1.1
    m = V.render_region(x0, y0, x1, y1, tile, t=t, opened_doors="ABC", player=(32, 79))
    # void wind telegraph: streaks sweeping west→east across the bridge
    streak = pygame.Surface(m.get_size(), pygame.SRCALPHA)
    for k in range(9):
        yy = (72 - y0) * tile + k * 45 + 10
        xx = (20 - x0) * tile + (k * 97) % 300
        pygame.draw.line(streak, (200, 160, 255, 120), (xx, yy), (xx + 260, yy + 16), 3)
        pygame.draw.line(streak, (240, 220, 255, 170), (xx + 200, yy + 12), (xx + 260, yy + 16), 3)
    m.blit(streak, (0, 0))
    V.nameplate(m, "VOID WIND in 2s: stand on a rune!", (32 - x0) * tile + tile // 2 + 150, (78 - y0) * tile, (230, 200, 255), F[14])
    # shrine / warning labels
    V.nameplate(m, "Healing Shrine (checkpoint)", (32 - x0) * tile + 16, (70 - y0) * tile - 44, (150, 255, 190), F[12])
    V.nameplate(m, "Warning stone", (30 - x0) * tile - 30, (71 - y0) * tile + 6, (255, 220, 130), F[11])
    zone_banner(m, m.get_width() // 2, 8, "The Narrow Way", "Void wind · Nyxarath waits beyond")
    boss_bar(m, m.get_width() // 2, m.get_height() - 70, "Nyxarath, the Hollow Eclipse  ·  lv 110", 0.58, "Phase 2 of 3: Rift Tide")
    # warning prompt mock
    pr = pygame.Rect(22, 150, 330, 118)
    panel(m, pr, "Beyond lies Nyxarath", (230, 190, 90))
    for i, line in enumerate(["The bridge is narrow and the wind is cruel.",
                              "Recommended: combat 90+, food, anti-void ward.",
                              "[ Cross ]     [ Not yet ]"]):
        m.blit(F[12].render(line, True, (230, 220, 240)), (pr.x + 12, pr.y + 38 + i * 24))
    pygame.image.save(m, os.path.join(OUT, "void_bridge_boss_closeup.png"))


def secret_before_after():
    tile = 40
    x0, y0, x1, y1 = 11, 3, 31, 13
    before = V.render_region(x0, y0, x1, y1, tile, t=0.6, show_mons=False, player=(25, 8))
    after = V.render_region(x0, y0, x1, y1, tile, t=0.6, show_mons=False, opened_secrets=("reliquary",), player=(21, 8))
    zoom = pygame.transform.scale(before.subsurface(pygame.Rect((22 - x0) * tile, (7 - y0) * tile, tile * 3, tile * 3)).copy(), (tile * 6, tile * 6))
    # hover tooltip on the cracked wall
    wx, wy = (23 - x0) * tile + tile // 2, (8 - y0) * tile
    tip = pygame.Rect(wx - 150, wy - 64, 300, 50)
    panel(before, tip, None, (200, 180, 120))
    before.blit(F[13].render("Search  Cracked wall", True, (255, 230, 150)), (tip.x + 10, tip.y + 6))
    before.blit(F[11].render("A draught whistles through a crack in the stone.", True, (220, 215, 230)), (tip.x + 10, tip.y + 28))
    before.blit(zoom, (20, before.get_height() - tile * 6 - 20))
    pygame.draw.rect(before, (255, 210, 110), (20, before.get_height() - tile * 6 - 20, tile * 6, tile * 6), 2)
    before.blit(F[12].render("2x zoom of the hint", True, (255, 210, 110)), (26, before.get_height() - tile * 6 - 40))
    chat = pygame.Rect(8, after.get_height() - 44, 520, 36)
    panel(after, chat, None, (200, 180, 120))
    after.blit(F[12].render("You push the loose stones. A hidden passage grinds open!", True, (255, 230, 150)), (chat.x + 10, chat.y + 10))
    W_, H_ = before.get_width(), before.get_height()
    img = pygame.Surface((W_ * 2 + 30, H_ + 50))
    img.fill((14, 10, 20))
    img.blit(F[18].render("BEFORE: subtle hint (crack, chips, drifting motes); room hidden", True, (235, 215, 255)), (10, 12))
    img.blit(F[18].render("AFTER: searched; Hidden Reliquary revealed (chest, loot, lore)", True, (235, 215, 255)), (W_ + 30, 12))
    img.blit(before, (10, 44))
    img.blit(after, (W_ + 20, 44))
    # 1x crop of the hint at game scale inset
    pygame.image.save(img, os.path.join(OUT, "void_secret_wall_before_after.png"))


def door_and_key():
    tile = 40
    x0, y0, x1, y1 = 24, 25, 40, 36
    locked = V.render_region(x0, y0, x1, y1, tile, t=0.9, show_mons=False, player=(32, 29))
    opened = V.render_region(x0, y0, x1, y1, tile, t=0.9, show_mons=False, player=(32, 33), opened_doors="A")
    tip = pygame.Rect(20, 16, 440, 56)
    panel(locked, tip, None, V.KEY_COL["A"])
    locked.blit(F[13].render("Unlock  Amethyst Seal", True, (230, 200, 255)), (tip.x + 10, tip.y + 6))
    locked.blit(F[11].render("Locked. It needs an Amethyst Key; the Gallery Warden carries one.", True, (220, 215, 230)), (tip.x + 10, tip.y + 30))
    chat = pygame.Rect(8, opened.get_height() - 44, 560, 36)
    panel(opened, chat, None, V.KEY_COL["A"])
    opened.blit(F[12].render("The Amethyst Key dissolves; the seal opens (for you only).", True, (230, 200, 255)), (chat.x + 10, chat.y + 10))
    W_, H_ = locked.get_width(), locked.get_height()
    kw = 360
    img = pygame.Surface((W_ * 2 + kw + 40, H_ + 50))
    img.fill((14, 10, 20))
    img.blit(F[18].render("Locked seal (door A)", True, (235, 215, 255)), (10, 12))
    img.blit(F[18].render("Unlocked with the key", True, (235, 215, 255)), (W_ + 20, 12))
    img.blit(locked, (10, 44))
    img.blit(opened, (W_ + 20, 44))
    K = pygame.Rect(W_ * 2 + 30, 44, kw, H_)
    panel(img, K, "Dungeon keys (bound to the visit)")
    y = K.y + 46
    for ch, (_, _, key, nm) in V.MAP["doors"].items():
        slot = pygame.Rect(K.x + 14, y, 64, 64)
        pygame.draw.rect(img, (40, 34, 30), slot)
        pygame.draw.rect(img, (90, 80, 60), slot, 2)
        V.draw_key_icon(img, slot.centerx + 2, slot.centery, 44, V.KEY_COL[ch])
        name = {"A": "Amethyst Key", "B": "Obsidian Key", "C": "Rift Sigil"}[ch]
        src = {"A": "Drop: Gallery Warden (100%)", "B": "Secret: Quartermaster's Cache",
               "C": "Drop: Knight-Captain Vorn (100%)"}[ch]
        img.blit(F[14].render(name, True, V.KEY_COL[ch]), (slot.right + 12, y + 6))
        img.blit(F[11].render(src, True, (220, 215, 230)), (slot.right + 12, y + 28))
        img.blit(F[11].render(f"Opens {nm} (door {ch})", True, (190, 185, 200)), (slot.right + 12, y + 44))
        y += 86
    # 1x game-scale key icons (inventory is 36 px)
    img.blit(F[12].render("Inventory scale (36 px):", True, (220, 215, 230)), (K.x + 14, y + 4))
    for i, ch in enumerate("ABC"):
        slot = pygame.Rect(K.x + 14 + i * 44, y + 26, 36, 36)
        pygame.draw.rect(img, (40, 34, 30), slot)
        V.draw_key_icon(img, slot.centerx + 1, slot.centery, 26, V.KEY_COL[ch])
    pygame.image.save(img, os.path.join(OUT, "void_locked_door_and_key.png"))


def zone_strip():
    """One game-scale (TILE 40) crop per zone, with monsters and labels, plus a fog-of-war mock."""
    tile = 40
    crops = [("Entry Hall · lv 55", (24, 3, 40, 13), (32, 5)),
             ("Shattered Galleries · lv 62–68", (39, 18, 57, 30), None),
             ("Hollow Barracks · lv 70–78", (26, 34, 54, 46), None),
             ("Crystal Depths · lv 82–92", (4, 49, 26, 59), None),
             ("The Rift Edge · lv 91–95", (14, 62, 40, 71), None)]
    imgs = []
    for title, (x0, y0, x1, y1), pl in crops:
        s = V.render_region(x0, y0, x1, y1, tile, t=0.7, opened_doors="ABC", player=pl)
        if title.startswith("Entry"):
            zone_banner(s, s.get_width() // 2, 70, "Entry Hall", "The Void Sanctum · Lv 50s")
        sc = 560 / s.get_width()
        s = pygame.transform.smoothscale(s, (560, int(s.get_height() * sc)))
        imgs.append((title, s))
    # fog mock: entry + galleries with fog of war
    fog = V.render_region(4, 2, 60, 32, 14, t=0.7, markers=True, fog=(32, 20, 9), opened_doors="")
    fsc = 560 / fog.get_width()
    fog = pygame.transform.smoothscale(fog, (560, int(fog.get_height() * fsc)))
    imgs.append(("Fog of war (explored radius; minimap follows)", fog))
    cols = 2
    rows = (len(imgs) + 1) // 2
    hmax = max(i[1].get_height() for i in imgs)
    img = pygame.Surface((cols * 580 + 10, rows * (hmax + 36) + 10))
    img.fill((14, 10, 20))
    for i, (title, s) in enumerate(imgs):
        x = 10 + (i % cols) * 580
        y = 10 + (i // cols) * (hmax + 36)
        img.blit(F[16].render(title, True, (235, 215, 255)), (x, y))
        img.blit(s, (x, y + 26))
    pygame.image.save(img, os.path.join(OUT, "void_zones_gamescale.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    msgs, checks = V.validate()
    print("spawn issues:", msgs, "checks:", all(checks.values()))
    full_map()
    bridge_closeup()
    secret_before_after()
    door_and_key()
    zone_strip()
    print("done")
