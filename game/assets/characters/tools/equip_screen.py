"""Render the real Equipment & Stats modal (old vs new) headless via GameClient's own method."""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
REPO = os.environ.get("MYTHO_REPO", "/workspace/mythoscape_chars")
CL = os.path.join(REPO, "game/assets/mmorpg/client")
sys.path.insert(0, CL)
os.chdir(CL)
import pygame
pygame.init()
screen = pygame.display.set_mode((960, 640))
import types; sys.modules.setdefault("websockets", types.ModuleType("websockets"))
import client as C
import rs_humanoid, procedural_sprites_finished as PS

OUT = sys.argv[1]


class Stub:
    pass


def make(eq, gender="male"):
    s = Stub()
    s.screen = screen
    ui = pygame.font.match_font("arial,helvetica,segoe ui,dejavu sans") or None
    s.font = pygame.font.SysFont(ui, 20); s.font_small = pygame.font.SysFont(ui, 18)
    s.font_big = pygame.font.SysFont(ui, 30, bold=True); s.font_tiny = pygame.font.SysFont(ui, 15)
    s.player = {"name": "esteph", "gender": gender, "equipment": eq, "hp": 41, "max_hp": 52,
                "levels": {"attack": 40, "strength": 38, "defence": 35, "archery": 22, "hitpoints": 52, "karma": 4},
                "inventory": {"0": {"item_id": "iron_arrow", "qty": 120}}, "quiver_total": 340, "quiver_best": "steel_arrow"}
    s.player_combat_level = lambda: 51
    s.player_total_level = lambda: 412
    s.draw_hp_bar = lambda cx, y, hp, mx: C.GameClient.draw_hp_bar(s, cx, y, hp, mx)
    return s


def bg():
    screen.fill((40, 52, 36))
    for y in range(0, 640, 40):
        for x in range(0, 960, 40):
            if (x // 40 + y // 40) % 2:
                screen.fill((46, 60, 40), (x, y, 40, 40))


SETS = {
    "empty": ({}, "female"),
    "steel": ({"weapon": "steel_longsword", "shield": "steel_shield", "body": "steel_body", "legs": "steel_legs",
               "helmet": "steel_helmet", "amulet": "sapphire_amulet", "ring": "ruby_ring", "ammo": "arrow_quiver"}, "male"),
    "mythos": ({"weapon": "mythos_longsword", "shield": "mythos_shield", "body": "mythos_body", "legs": "mythos_legs",
                "helmet": "mythos_helmet", "amulet": "void_amulet", "ring": "void_ring", "ammo": "iron_arrow"}, "male"),
    "eclipse": ({"weapon": "eclipse_cleaver", "shield": "eclipse_shield", "body": "eclipse_body", "legs": "eclipse_legs",
                 "helmet": "eclipse_helmet", "amulet": "void_amulet", "ring": "void_ring", "ammo": "iron_arrow"}, "male"),
    "archer_f": ({"weapon": "yew_shortbow", "body": "leather_body", "legs": "leather_chaps", "helmet": "leather_cowl",
                  "amulet": "emerald_amulet", "ammo": "iron_arrow"}, "female"),
}
for name, (eq, g) in SETS.items():
    for new in (False, True):
        C.USE_NEW_EQUIPMENT_UI = new
        rs_humanoid.USE_NEW_CHARACTERS = new
        PS.USE_NEW_ITEM_ICONS = new
        st = make(eq, g)
        bg()
        pygame.mouse.set_pos((90 + 14 + 0, 0))
        C.GameClient.draw_equipment_modal(st)
        pygame.image.save(screen, os.path.join(OUT, f"equip_{name}_{'after' if new else 'before'}.png"))
        assert set(st.equip_slot_rects) == {"helmet", "amulet", "ring", "weapon", "ammo", "shield", "body", "legs"}
print("ok")
