"""Headless screenshots of the Equipment & Stats modal -> tests/_out/equip_<case>.png

Run: python3 tests/equipment_modal_shots.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, os.path.join(ROOT, "server"))

import pygame  # noqa: E402
from content import ITEMS  # noqa: E402
import equipment_ui_v2  # noqa: E402

CASES = {
    "a_eclipse_sword": {"helmet": "eclipse_helmet", "body": "eclipse_body", "legs": "eclipse_legs", "weapon": "eclipse_sword"},
    "b_eclipse_cleaver": {"helmet": "eclipse_helmet", "body": "eclipse_body", "legs": "eclipse_legs", "weapon": "eclipse_cleaver"},
    "c_mythos": {"helmet": "mythos_helmet", "body": "mythos_body", "legs": "mythos_legs", "weapon": "mythos_longsword"},
    "d_mithril_full": {"helmet": "mithril_helmet", "body": "mithril_body", "legs": "mithril_legs", "weapon": "mithril_battleaxe"},
    "d2_mithril_partial": {"helmet": "mithril_helmet", "body": "mithril_body"},
    "e_steel": {"helmet": "steel_helmet", "body": "steel_body", "legs": "steel_legs", "weapon": "steel_longsword"},
}


class Fake:
    def __init__(self, eq, gender):
        self.screen = pygame.display.set_mode((940, 640))
        self.font_big = pygame.font.Font(None, 30)
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        self.font_tiny = pygame.font.Font(None, 16)
        self.player = {"id": 1, "name": "David", "gender": gender, "equipment": eq, "hp": 99, "max_hp": 99,
                       "levels": {"attack": 80, "strength": 80, "defence": 80, "karma": 1}, "inventory": {}}

    def player_combat_level(self):
        return 100

    def player_total_level(self):
        return 900

    def draw_hp_bar(self, x, y, hp, mx):
        pygame.draw.rect(self.screen, (0, 200, 0), (x - 30, y, 60, 6))


def main():
    pygame.init()
    out = os.path.join(HERE, "_out")
    os.makedirs(out, exist_ok=True)
    paths = []
    for gender in ("male", "female"):
        for name, eq in CASES.items():
            f = Fake(eq, gender)
            f.screen.fill((40, 60, 40))
            equipment_ui_v2.draw(f, ITEMS, lambda s, k: {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}, None, None)
            path = os.path.join(out, f"equip_{name}_{gender}.png")
            pygame.image.save(f.screen, path)
            paths.append(path)
    print("\n".join(paths))


if __name__ == "__main__":
    main()
