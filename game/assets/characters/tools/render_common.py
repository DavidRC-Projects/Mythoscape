import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
REPO = os.environ.get("MYTHO_REPO", "/workspace/mythoscape_chars")
CH = os.path.join(REPO, "game/assets/characters")
sys.path.insert(0, CH)
sys.path.insert(0, os.path.join(REPO, "game/assets/mmorpg/server"))
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import rs_humanoid as H
import procedural_sprites_finished as PS
import content
ITEMS = content.ITEMS
BG = (46, 58, 40)
GRASS2 = (52, 66, 44)


def weapon_style(item_id):
    if not item_id:
        return None
    if "bow" in item_id:
        return "bow"
    for k in ("dagger", "pickaxe"):
        if k in item_id:
            return k
    if "battleaxe" in item_id or "cleaver" in item_id:
        return "battleaxe"
    if "axe" in item_id:
        return "axe"
    return "sword"


def draw_char(surf, cx, cy, tile, new, eq=None, gender="male", facing=1, moving=False, t=0.0, attacking=0.0,
              action=None, body=(70, 210, 90), skin=(235, 195, 150), hair=(70, 45, 30), robe=False):
    eq = eq or {}
    H.USE_NEW_CHARACTERS = bool(new)
    PS.draw_humanoid_detailed(surf, cx, cy, tile, body, skin, hair, weapon=weapon_style(eq.get("weapon")),
                              shield=bool(eq.get("shield")), moving=moving, t=t, robe=robe, facing=facing,
                              equipment=eq, attacking=attacking, action=action, gender=gender)
    H.USE_NEW_CHARACTERS = False


def tiles(surf, tile=40):
    w, h = surf.get_size()
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            surf.fill(BG if (x // tile + y // tile) % 2 else GRASS2, (x, y, tile, tile))


_font = None


def label(surf, text, x, y, col=(235, 225, 190), size=14):
    global _font
    f = pygame.font.SysFont("dejavusans", size)
    surf.blit(f.render(text, True, col), (x, y))
