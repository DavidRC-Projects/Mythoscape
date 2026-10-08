"""
equipment_ui_v2.py — USE_NEW_EQUIPMENT_UI Equipment & Stats screen.

Same modal rect (90,36,760,560) so handle_equipment_click()'s click-outside
close still works; same self.equip_slot_rects keys (click slot = UNEQUIP);
same data (gear_bonuses / karma_bonuses / stat_boosts / levels / quiver);
same hover detail text and the same Esc / E behaviour (handled by the caller).
"""
import math
import pygame

GOLD = (212, 176, 92)
GOLD_D = (130, 100, 48)
STONE = (58, 52, 44)
STONE_D = (38, 34, 29)
STONE_L = (86, 78, 64)
INK = (22, 18, 14)
TEXT = (236, 226, 200)
MUTED = (170, 160, 140)
ORANGE = (255, 152, 31)          # OSRS-ish yellow/orange headings

# Paper-doll positions (relative to the stage rect): OSRS-like cross layout
DOLL = {
    "helmet": (0.5, 0.075),
    "amulet": (0.14, 0.25), "ammo": (0.86, 0.25),
    "weapon": (0.14, 0.44), "shield": (0.86, 0.44),
    "body": (0.14, 0.63), "legs": (0.86, 0.63),
    "ring": (0.5, 0.925),
}
# where each slot's guide line lands on the doll (fraction of stage)
ANCHOR = {"helmet": (0.5, 0.25), "amulet": (0.5, 0.33), "ammo": (0.58, 0.36), "weapon": (0.36, 0.52),
          "shield": (0.64, 0.52), "body": (0.46, 0.45), "legs": (0.54, 0.65), "ring": (0.62, 0.64)}


def _bevel(surf, rect, fill=STONE, light=STONE_L, dark=STONE_D, w=2):
    pygame.draw.rect(surf, fill, rect)
    for i in range(w):
        pygame.draw.line(surf, light, (rect.x + i, rect.y + i), (rect.right - 1 - i, rect.y + i))
        pygame.draw.line(surf, light, (rect.x + i, rect.y + i), (rect.x + i, rect.bottom - 1 - i))
        pygame.draw.line(surf, dark, (rect.x + i, rect.bottom - 1 - i), (rect.right - 1 - i, rect.bottom - 1 - i))
        pygame.draw.line(surf, dark, (rect.right - 1 - i, rect.y + i), (rect.right - 1 - i, rect.bottom - 1 - i))
    pygame.draw.rect(surf, INK, rect, 1)


def _inset(surf, rect, fill=(30, 27, 23)):
    _bevel(surf, rect, fill, STONE_D, STONE_L, 2)


def _panel_texture(surf, rect, seed=7):
    # subtle stone speckle so the panel isn't a flat slab
    import random
    rnd = random.Random(seed)
    for _ in range(rect.w * rect.h // 90):
        x = rect.x + rnd.randrange(rect.w)
        y = rect.y + rnd.randrange(rect.h)
        c = rnd.choice(((64, 57, 48), (52, 46, 39), (70, 63, 52)))
        surf.set_at((x, y), c)


def _silhouette(surf, slot, r, col=(78, 70, 58)):
    """Faded slot glyph for empty slots (OSRS-style)."""
    cx, cy = r.center
    u = r.w / 16.0
    P = lambda x, y: (int(cx + x * u), int(cy + y * u))
    if slot == "helmet":
        pygame.draw.polygon(surf, col, [P(-4.5, 3), P(-4.5, -1), P(-2.6, -4.4), P(0, -5.2), P(2.6, -4.4), P(4.5, -1), P(4.5, 3), P(2.6, 3), P(2.6, 0), P(-2.6, 0), P(-2.6, 3)])
    elif slot == "amulet":
        pygame.draw.arc(surf, col, pygame.Rect(P(-4.5, -6)[0], P(0, -6)[1], int(9 * u), int(9 * u)), math.pi, 2 * math.pi, max(2, int(u)))
        pygame.draw.lines(surf, col, False, [P(-4.5, -1.5), P(0, 2.5), P(4.5, -1.5)], max(2, int(u)))
        pygame.draw.circle(surf, col, P(0, 4), int(2.2 * u))
    elif slot == "ammo":
        for o in (-2.5, 0, 2.5):
            pygame.draw.line(surf, col, P(-4 + o, 5), P(4 + o, -5), max(2, int(u)))
            pygame.draw.polygon(surf, col, [P(4 + o, -5), P(2 + o, -4.4), P(3.4 + o, -3)])
    elif slot == "weapon":
        pygame.draw.polygon(surf, col, [P(-5, 5), P(-3.6, 5.6), P(4.8, -2.8), P(5.4, -5.4), P(2.8, -4.8), P(-5.6, 3.6)])
        pygame.draw.line(surf, col, P(-4.6, 1.2), P(-1.2, 4.6), max(2, int(u * 1.4)))
    elif slot == "shield":
        pygame.draw.polygon(surf, col, [P(-4.6, -5), P(4.6, -5), P(4.2, 0.6), P(0, 6), P(-4.2, 0.6)])
    elif slot == "body":
        pygame.draw.polygon(surf, col, [P(-3, -5.4), P(0, -4), P(3, -5.4), P(6, -3.4), P(6, 1), P(3.6, 1), P(3.4, 5.6), P(-3.4, 5.6), P(-3.6, 1), P(-6, 1), P(-6, -3.4)])
    elif slot == "legs":
        pygame.draw.polygon(surf, col, [P(-4, -5.6), P(4, -5.6), P(4.6, 5.6), P(1.2, 5.6), P(0, -1), P(-1.2, 5.6), P(-4.6, 5.6)])
    elif slot == "ring":
        pygame.draw.circle(surf, col, P(0, 1), int(4.2 * u), max(2, int(u * 1.3)))
        pygame.draw.circle(surf, col, P(0, -3.6), int(1.8 * u))


def _icon(surf, rect, item_id, items, sprites):
    try:
        import gear_v2
        if gear_v2.draw_icon(surf, rect, item_id, items):
            return
    except Exception:
        pass
    sprites.draw_item_icon(surf, rect, item_id, items)


def draw(self, ITEMS, karma_slot_bonus, sprites, weapon_style):
    scr = self.screen
    box = pygame.Rect(90, 36, 760, 560)
    # dim the world behind
    shade = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 110))
    scr.blit(shade, (0, 0))
    _bevel(scr, box, STONE, (96, 86, 70), (26, 23, 19), 3)
    _panel_texture(scr, box.inflate(-8, -8))
    pygame.draw.rect(scr, GOLD_D, box.inflate(-8, -8), 1)
    # title bar
    tb = pygame.Rect(box.x + 10, box.y + 8, box.w - 20, 36)
    _inset(scr, tb, (44, 38, 31))
    title = self.font_big.render("Equipment & Stats", True, ORANGE)
    scr.blit(self.font_big.render("Equipment & Stats", True, INK), (tb.x + 13, tb.y + 3))
    scr.blit(title, (tb.x + 12, tb.y + 2))
    name = (self.player or {}).get("name") or "You"
    cmb = self.player_combat_level()
    nm = self.font.render(f"{name}  ·  Combat {cmb}", True, TEXT)
    scr.blit(nm, (tb.right - nm.get_width() - 14, tb.y + 8))

    eq = self.player.get("equipment") or {}
    karma_lvl = (self.player.get("levels") or {}).get("karma", 1)
    bonuses = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    for slot in ("helmet", "amulet", "ring", "weapon", "ammo", "shield", "body", "legs"):
        item_id = eq.get(slot)
        if not item_id:
            continue
        item = ITEMS.get(item_id) or {}
        kb = karma_slot_bonus(slot, karma_lvl)
        for k in bonuses:
            bonuses[k] += int(item.get(k, 0) or 0) + int(kb.get(k, 0) or 0)

    # ---------------- paper doll stage ----------------
    stage = pygame.Rect(box.x + 14, box.y + 52, 348, 392)
    _inset(scr, stage, (34, 30, 26))
    # soft vignette floor + backdrop arch
    arch = pygame.Rect(stage.centerx - 92, stage.y + 34, 184, 320)
    pygame.draw.ellipse(scr, (40, 36, 30), arch)
    floor = pygame.Rect(stage.centerx - 62, stage.y + 296, 124, 22)
    pygame.draw.ellipse(scr, (26, 23, 20), floor)
    pygame.draw.ellipse(scr, GOLD_D, floor, 1)

    mx, my = pygame.mouse.get_pos()
    slot_px = 46
    self.equip_slot_rects = {}
    rects = {}
    for slot, (fx, fy) in DOLL.items():
        r = pygame.Rect(0, 0, slot_px, slot_px)
        r.center = (int(stage.x + fx * stage.w), int(stage.y + fy * stage.h))
        rects[slot] = r
    # guide lines (behind the doll)
    for slot, r in rects.items():
        ax, ay = ANCHOR[slot]
        pygame.draw.line(scr, (62, 56, 46), r.center, (int(stage.x + ax * stage.w), int(stage.y + ay * stage.h)), 1)

    # character (same call as the old preview; smaller so slots fit around it)
    body, skin, hair = (70, 210, 90), (235, 195, 150), (70, 45, 30)
    gender = (self.player or {}).get("gender") or "male"
    sprites.draw_humanoid_detailed(
        scr, stage.centerx, stage.y + 196, 80, body, skin, hair,
        weapon=weapon_style(eq.get("weapon")), shield=bool(eq.get("shield")),
        moving=False, t=0.0, facing=1, equipment=eq, attacking=0.0, action="stand", gender=gender,
    )

    hover_slot = None
    inv = self.player.get("inventory") or {}
    for slot, r in rects.items():
        item_id = eq.get(slot)
        hov = r.collidepoint(mx, my)
        if hov:
            hover_slot = slot
        _bevel(scr, r, (70, 62, 50) if item_id else (52, 47, 39), STONE_L, STONE_D, 2)
        inner = r.inflate(-8, -8)
        if item_id:
            _icon(scr, inner, item_id, ITEMS, sprites)
            if slot == "ammo":
                if item_id == "arrow_quiver":
                    qn = int((self.player or {}).get("quiver_total") or 0)
                else:
                    qn = sum(int(e.get("qty") or 0) for e in inv.values() if e and e.get("item_id") == item_id)
                q = self.font_tiny.render(str(qn), True, (255, 255, 0))
                scr.blit(self.font_tiny.render(str(qn), True, INK), (r.x + 4, r.y + 2))
                scr.blit(q, (r.x + 3, r.y + 1))
        else:
            _silhouette(scr, slot, inner)
        if hov:
            pygame.draw.rect(scr, GOLD, r, 2)
        self.equip_slot_rects[slot] = r

    # hp bar under the doll (as before)
    self.draw_hp_bar(stage.centerx, floor.bottom + 2, self.player["hp"], self.player["max_hp"])

    # ---------------- detail box (hover / first worn) ----------------
    detail_slot = hover_slot
    if detail_slot is None:
        for prefer in ("weapon", "body", "helmet", "shield", "legs", "amulet", "ring", "ammo"):
            if eq.get(prefer):
                detail_slot = prefer
                break
    det = pygame.Rect(box.x + 14, stage.bottom + 6, stage.w, 70)
    _inset(scr, det, (30, 27, 23))
    if detail_slot:
        item_id = eq.get(detail_slot)
        item = ITEMS.get(item_id) if item_id else None
        if item:
            ic = pygame.Rect(det.x + 8, det.y + 11, 48, 48)
            _bevel(scr, ic, (70, 62, 50), STONE_L, STONE_D, 2)
            _icon(scr, ic.inflate(-8, -8), item_id, ITEMS, sprites)
            label_name = item["name"]
            if detail_slot == "ammo" and item_id == "arrow_quiver":
                qtot = int((self.player or {}).get("quiver_total") or 0)
                label_name = f"Arrow Quiver  ·  {qtot} arrows"
            elif detail_slot == "ammo":
                qty = sum(int(e.get("qty") or 0) for e in inv.values() if e and e.get("item_id") == item_id)
                label_name = f"{item['name']}  ×{qty}"
            scr.blit(self.font_small.render(label_name, True, ORANGE), (det.x + 64, det.y + 6))
            kb = karma_slot_bonus(detail_slot, karma_lvl)
            if detail_slot == "ammo" and item_id == "arrow_quiver":
                best = (self.player or {}).get("quiver_best")
                best_item = ITEMS.get(best) or {}
                detail = (f"Fires best first · next: {best_item.get('name', '—')}  "
                          f"(+{best_item.get('ranged_att', 0)} att / +{best_item.get('ranged_str', 0)} str)")
            elif detail_slot == "ammo":
                detail = f"Ranged +{item.get('ranged_att', 0)} att / +{item.get('ranged_str', 0)} str"
            else:
                detail = (f"Att +{item.get('att_bonus', 0)}(+{kb['att_bonus']}k)   "
                          f"Str +{item.get('str_bonus', 0)}(+{kb['str_bonus']}k)   "
                          f"Def +{item.get('def_bonus', 0)}(+{kb['def_bonus']}k)")
            scr.blit(self.font_tiny.render(detail, True, TEXT), (det.x + 64, det.y + 28))
            scr.blit(self.font_tiny.render(f"{detail_slot.title()} slot  ·  Click slot to unequip", True, MUTED), (det.x + 64, det.y + 47))
        else:
            scr.blit(self.font_small.render(f"{detail_slot.title()}: empty", True, MUTED), (det.x + 12, det.y + 24))
    else:
        scr.blit(self.font_small.render("No gear equipped — wear items from inventory", True, MUTED), (det.x + 12, det.y + 24))

    # ---------------- stats panel ----------------
    panel = pygame.Rect(box.x + 372, box.y + 52, 374, 468)
    _inset(scr, panel, (34, 30, 26))
    levels = self.player.get("levels") or {}
    wb = self.player.get("gear_bonuses") or bonuses
    kb_tot = self.player.get("karma_bonuses") or {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    pot = self.player.get("stat_boosts") or {}
    x0, y = panel.x + 14, panel.y + 10
    scr.blit(self.font.render("Worn bonuses", True, ORANGE), (x0, y))
    y += 28

    def glyph(kind, cx, cy, col):
        u = 1.6
        if kind == "att":
            pygame.draw.line(scr, col, (cx - 6 * u, cy + 6 * u), (cx + 6 * u, cy - 6 * u), 3)
            pygame.draw.line(scr, col, (cx - 6 * u, cy + 1 * u), (cx - 1 * u, cy + 6 * u), 3)
        elif kind == "str":
            pygame.draw.circle(scr, col, (int(cx), int(cy)), int(5 * u))
            pygame.draw.rect(scr, col, (cx - 5 * u, cy - 7 * u, 10 * u, 5 * u))
        elif kind == "def":
            pygame.draw.polygon(scr, col, [(cx - 6 * u, cy - 6 * u), (cx + 6 * u, cy - 6 * u), (cx + 5 * u, cy + 1 * u), (cx, cy + 7 * u), (cx - 5 * u, cy + 1 * u)])
        else:  # ranged
            pygame.draw.arc(scr, col, pygame.Rect(cx - 7 * u, cy - 7 * u, 10 * u, 14 * u), -math.pi / 2, math.pi / 2, 3)
            pygame.draw.line(scr, col, (cx - 2 * u, cy - 7 * u), (cx - 2 * u, cy + 7 * u), 1)

    rows = (("Attack", "att_bonus", (214, 112, 84), "att"), ("Strength", "str_bonus", (220, 170, 70), "str"),
            ("Defence", "def_bonus", (110, 150, 200), "def"))
    for lab, key, col, g in rows:
        val = int(wb.get(key, 0))
        card = pygame.Rect(x0, y, panel.w - 28, 40)
        _bevel(scr, card, (48, 43, 36), STONE_L, STONE_D, 1)
        glyph(g, card.x + 20, card.centery, col)
        scr.blit(self.font_small.render(lab, True, TEXT), (card.x + 40, card.y + 3))
        kv = int(kb_tot.get(key, 0) or 0)
        scr.blit(self.font_tiny.render(f"karma +{kv}", True, MUTED), (card.x + 40, card.y + 21))
        vs = self.font.render(f"+{val}", True, col)
        scr.blit(vs, (card.right - vs.get_width() - 10, card.y + 9))
        # segmented bar (10 segments of 20)
        bx, bw = card.x + 132, card.w - 132 - 60
        for i in range(10):
            seg = pygame.Rect(bx + i * (bw // 10), card.y + 16, bw // 10 - 2, 8)
            fill = max(0.0, min(1.0, (val - i * 20) / 20.0))
            pygame.draw.rect(scr, (28, 25, 21), seg)
            if fill > 0:
                pygame.draw.rect(scr, col, (seg.x, seg.y, int(seg.w * fill), seg.h))
            pygame.draw.rect(scr, INK, seg, 1)
        y += 44
    ra, rsb = int(wb.get("ranged_att", 0) or 0), int(wb.get("ranged_str", 0) or 0)
    card = pygame.Rect(x0, y, panel.w - 28, 30)
    _bevel(scr, card, (48, 43, 36), STONE_L, STONE_D, 1)
    glyph("rng", card.x + 22, card.centery, (130, 180, 110))
    scr.blit(self.font_small.render(f"Ranged   +{ra} att  /  +{rsb} str", True, TEXT), (card.x + 40, card.y + 5))
    y += 40

    scr.blit(self.font.render("Combat levels", True, ORANGE), (x0, y))
    y += 26

    def combat_line(label, skill, gear_key):
        base = int(levels.get(skill, 1))
        b = pot.get(skill) or {}
        amt = int(b.get("amount") or 0)
        gear = int(wb.get(gear_key, 0))
        if amt > 0:
            return f"{label}", f"{base + amt}", f"base {base}  pot +{amt}  gear +{gear}"
        return f"{label}", f"{base}", f"gear +{gear}"

    items = []
    for skill_label, skill, gkey in (("Attack", "attack", "att_bonus"), ("Strength", "strength", "str_bonus"),
                                     ("Defence", "defence", "def_bonus"), ("Archery", "archery", "att_bonus"),
                                     ("Hitpoints", "hitpoints", "def_bonus")):
        if skill == "hitpoints":
            items.append(("Hitpoints", f"{self.player['hp']}/{self.player['max_hp']}", "top 3 combat skills"))
        elif skill == "archery":
            items.append(("Archery", f"{int(levels.get('archery', 1))}", f"ranged +{ra} att / +{rsb} str"))
        else:
            items.append(combat_line(skill_label, skill, gkey))
    cw = (panel.w - 34) // 2
    for i, (lab, val, sub) in enumerate(items):
        cx = x0 + (i % 2) * (cw + 6)
        cy = y + (i // 2) * 46
        c = pygame.Rect(cx, cy, cw if i < 4 else panel.w - 28, 42)
        _bevel(scr, c, (44, 39, 33), STONE_L, STONE_D, 1)
        scr.blit(self.font_small.render(lab, True, TEXT), (c.x + 8, c.y + 3))
        v = self.font.render(val, True, (255, 255, 0))
        scr.blit(v, (c.right - v.get_width() - 8, c.y + 2))
        scr.blit(self.font_tiny.render(sub, True, MUTED), (c.x + 8, c.y + 22))
    y += 3 * 46 + 4
    pygame.draw.line(scr, GOLD_D, (x0, y), (panel.right - 14, y))
    y += 8
    scr.blit(self.font_small.render(
        f"Karma {levels.get('karma', 1)}   (+{kb_tot.get('att_bonus', 0)}a / +{kb_tot.get('str_bonus', 0)}s / +{kb_tot.get('def_bonus', 0)}d)",
        True, (200, 180, 240)), (x0, y))
    y += 24
    scr.blit(self.font_small.render(
        f"Combat {self.player_combat_level()}   ·   Total {self.player_total_level()}", True, (170, 230, 150)), (x0, y))

    ft = self.font_small.render("Hover a slot for details · Esc / E to close", True, MUTED)
    scr.blit(ft, (box.x + 20, box.bottom - 30))
