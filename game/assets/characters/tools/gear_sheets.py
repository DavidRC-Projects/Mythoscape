import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from render_common import *
import gear_v2 as G
OUT = sys.argv[1]
T = 40
SETS = [
    ("Unarmoured (M)", {}, "male"),
    ("Unarmoured (F)", {}, "female"),
    ("Leather + shortbow", {"body": "leather_body", "legs": "leather_chaps", "helmet": "leather_cowl", "weapon": "oak_shortbow", "ammo": "iron_arrow"}, "female"),
    ("Bronze chain + sword", {"body": "bronze_chainbody", "legs": "bronze_chainlegs", "helmet": "bronze_helmet", "weapon": "bronze_sword", "shield": "bronze_sq_shield"}, "male"),
    ("Iron plate + battleaxe", {"body": "iron_body", "legs": "iron_legs", "helmet": "iron_helmet", "weapon": "iron_battleaxe"}, "male"),
    ("Steel plate + kite", {"body": "steel_body", "legs": "steel_legs", "helmet": "steel_helmet", "weapon": "steel_longsword", "shield": "steel_shield"}, "female"),
    ("Mithril chain + dagger", {"body": "mithril_chainbody", "legs": "mithril_chainlegs", "helmet": "mithril_helmet", "weapon": "mithril_dagger", "shield": "mithril_sq_shield"}, "male"),
    ("Adamant plate", {"body": "adamant_body", "legs": "adamant_legs", "helmet": "adamant_helmet", "weapon": "adamant_sword", "shield": "adamant_shield"}, "male"),
    ("Mythos set", {"body": "mythos_body", "legs": "mythos_legs", "helmet": "mythos_helmet", "weapon": "mythos_longsword", "shield": "mythos_shield", "amulet": "ruby_amulet"}, "male"),
    ("Eclipse set", {"body": "eclipse_body", "legs": "eclipse_legs", "helmet": "eclipse_helmet", "weapon": "eclipse_cleaver", "shield": "eclipse_shield"}, "male"),
    ("Goblin mail", {"body": "goblin_mail", "weapon": "bronze_axe"}, "male"),
]


def gearsets(path, new_only=False):
    cw, ch = 120, 150
    rows = [("OLD", False), ("NEW", True)] if not new_only else [("NEW", True)]
    S = pygame.Surface((len(SETS) * cw, len(rows) * 2 * ch + 50))
    tiles(S)
    for c, (name, eq, g) in enumerate(SETS):
        label(S, name, c * cw + 4, 2, size=11)
        for r, (rn, new) in enumerate(rows):
            for k, f in enumerate(("front", 1)):
                draw_char(S, c * cw + 60, 20 + (r * 2 + k) * ch + 105, T, new, eq, g, f)
    for r, (rn, new) in enumerate(rows):
        label(S, rn, 2, 20 + r * 2 * ch + 20, (255, 220, 120) if new else (200, 200, 200))
    pygame.image.save(pygame.transform.scale(S, (S.get_width() * 2, S.get_height() * 2)), path)


def attacks(path):
    ws = ["steel_longsword", "eclipse_cleaver", "iron_dagger", "mithril_battleaxe", "maple_shortbow", "bronze_pickaxe"]
    ph = [0.0, 0.25, 0.42, 0.52, 0.7]
    cw, ch = 110, 140
    S = pygame.Surface((len(ph) * 2 * cw + 20, len(ws) * ch + 10)); tiles(S)
    for r, w in enumerate(ws):
        for k, new in enumerate((False, True)):
            for c, p in enumerate(ph):
                x = (k * len(ph) + c) * cw + 60 + (20 if k else 0)
                draw_char(S, x, r * ch + 100, T, new, {"weapon": w, "body": "steel_body", "legs": "steel_legs"}, "male", 1, attacking=p if p else 0.0)
        label(S, w, 4, r * ch + 4, size=11)
    label(S, "OLD  (attack progress 0 / .25 / .42 / .52 / .70)", 60, S.get_height() - 16, size=11)
    label(S, "NEW", len(ph) * cw + 80, S.get_height() - 16, (255, 220, 120), size=11)
    pygame.image.save(pygame.transform.scale(S, (S.get_width() * 2, S.get_height() * 2)), path)


def weapons(path):
    ids = [k for k, v in ITEMS.items() if v.get("equip_slot") == "weapon"]
    cols = 7
    cw, ch = 118, 150
    rows = (len(ids) + cols - 1) // cols
    S = pygame.Surface((cols * cw, rows * ch)); S.fill((38, 34, 30))
    for i, iid in enumerate(ids):
        x, y = (i % cols) * cw, (i // cols) * ch
        pygame.draw.rect(S, (58, 52, 44), (x + 4, y + 4, cw - 8, ch - 8), border_radius=4)
        G.draw_icon(S, pygame.Rect(x + 29, y + 12, 60, 60), iid, ITEMS)
        # held in hand (attack impact frame)
        draw_char(S, x + cw // 2 - 10, y + 105, 26, True, {"weapon": iid}, "male", 1, attacking=0.5)
        label(S, ITEMS[iid]["name"][:18], x + 8, y + ch - 20, size=10)
    pygame.image.save(pygame.transform.scale(S, (S.get_width() * 2, S.get_height() * 2)), path)


def armour_icons(path):
    ids = [k for k, v in ITEMS.items() if v.get("equip_slot") in ("helmet", "body", "legs", "shield", "ammo", "amulet", "ring")]
    cols = 12
    cw, ch = 74, 84
    rows = (len(ids) + cols - 1) // cols
    S = pygame.Surface((cols * cw, rows * ch)); S.fill((38, 34, 30))
    for i, iid in enumerate(ids):
        x, y = (i % cols) * cw, (i // cols) * ch
        pygame.draw.rect(S, (62, 56, 46), (x + 3, y + 3, cw - 6, ch - 6), border_radius=4)
        G.draw_icon(S, pygame.Rect(x + 13, y + 6, 48, 48), iid, ITEMS)
        label(S, ITEMS[iid]["name"][:13], x + 5, y + ch - 22, size=9)
    pygame.image.save(pygame.transform.scale(S, (S.get_width() * 2, S.get_height() * 2)), path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    gearsets(os.path.join(OUT, "gear_sets_before_after.png"))
    attacks(os.path.join(OUT, "combat_attacks_before_after.png"))
    weapons(os.path.join(OUT, "weapons_sheet.png"))
    armour_icons(os.path.join(OUT, "armour_jewellery_icons.png"))
