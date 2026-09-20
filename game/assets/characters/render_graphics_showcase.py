#!/usr/bin/env python3
"""
Graphics showcase — evaluates procedural MMORPG art quality.

Renders a composed world plate (terrain, water, trees, rocks, buildings,
characters, monsters, items) plus variant strips. Saves to _qa_review/.

Usage:
  python render_graphics_showcase.py
"""
from __future__ import annotations

import math
import os
import sys

# Headless-friendly
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import procedural_sprites_finished as sprites
import rs_style as rs

OUT = os.path.join(HERE, "_qa_review")
TILE = 40


def _bg(surf, color=(34, 48, 38)):
    surf.fill(color)


def _label(surf, text, x, y, color=(230, 225, 210)):
    font = pygame.font.SysFont("arial", 14, bold=True)
    img = font.render(text, True, color)
    surf.blit(img, (x, y))


def draw_terrain_block(surf, x0, y0, cols, rows, kind="grass", t=0.0):
    for gy in range(rows):
        for gx in range(cols):
            rect = pygame.Rect(x0 + gx * TILE, y0 + gy * TILE, TILE, TILE)
            wx, wy = gx + 10, gy + 10
            if kind == "grass":
                sprites.draw_grass(surf, rect, wx, wy)
            elif kind == "dirt":
                sprites.draw_path(surf, rect, wx, wy)
            elif kind == "stone":
                sprites.draw_floor(surf, rect, wx, wy, zone="mine")
            elif kind == "water":
                shores = {
                    "N": gy == 0,
                    "S": gy == rows - 1,
                    "W": gx == 0,
                    "E": gx == cols - 1,
                }
                sprites.draw_water_detailed(surf, rect, t, wx, wy, shores=shores)


def render_world_plate(path, t=1.2):
    W, H = 1100, 720
    surf = pygame.Surface((W, H))
    _bg(surf, (28, 36, 32))
    _label(surf, "MYTHOSCAPE — Graphics Showcase (procedural)", 16, 10)

    # Terrain bands
    draw_terrain_block(surf, 20, 40, 12, 8, "grass", t)
    draw_terrain_block(surf, 20 + 4 * TILE, 40 + 5 * TILE, 5, 3, "dirt", t)
    draw_terrain_block(surf, 520, 40, 8, 5, "water", t)
    draw_terrain_block(surf, 520, 40 + 5 * TILE, 8, 3, "stone", t)
    draw_terrain_block(surf, 860, 40, 5, 8, "grass", t)

    # Trees (3+ variants)
    for i, (tx, ty, var) in enumerate([(80, 200, 0), (160, 240, 1), (240, 190, 2), (100, 300, 0)]):
        sprites.draw_tree_detailed(surf, tx, ty, TILE, variant=var, t=t)

    # Rocks
    ores = [None, "copper_rock", "iron_rock", "mithril_rock", "coal_rock"]
    for i, ore in enumerate(ores):
        sprites.draw_rock_detailed(surf, 340 + i * 55, 280, TILE, variant=i, ore_type=ore)

    # Buildings
    sprites.draw_house(surf, (560, 280, 120, 110), style=0, t=t)
    sprites.draw_house(surf, (720, 300, 110, 100), style=1, t=t)
    sprites.draw_building_roof(surf, pygame.Rect(880, 80, 100, 90), kind="smithy", style=0)

    # Props
    sprites.draw_furnace(surf, 920, 280, TILE, t)
    sprites.draw_anvil(surf, 980, 300, TILE, t)
    sprites.draw_door(surf, 860, 320, TILE, open_=False, t=t)

    # Player + NPCs
    sprites.draw_humanoid_detailed(
        surf, 420, 420, TILE,
        body_color=(55, 130, 70), skin_color=(235, 195, 150), hair_color=(60, 40, 25),
        moving=True, t=t, facing=1,
        equipment={"weapon": "steel_sword", "shield": "wooden_shield"},
    )
    sprites.draw_humanoid_detailed(
        surf, 500, 430, TILE,
        body_color=(70, 100, 180), skin_color=(230, 180, 140), hair_color=(30, 20, 15),
        moving=False, t=t, facing=-1, robe=True,
    )
    sprites.draw_humanoid_detailed(
        surf, 560, 450, TILE,
        body_color=(160, 70, 70), skin_color=(245, 210, 170), hair_color=(90, 60, 30),
        moving=True, t=t + 0.4, facing=1, attacking=0.45,
        equipment={"weapon": "steel_battleaxe", "body": "iron_platebody", "helmet": "iron_helmet"},
    )
    sprites.draw_humanoid_detailed(
        surf, 640, 440, TILE,
        body_color=(140, 100, 50), skin_color=(220, 170, 130), hair_color=(40, 30, 20),
        moving=False, t=t, facing=1,
        equipment={"weapon": "bronze_pickaxe"},
    )

    # Monsters — spaced so silhouettes read clearly
    monsters = [
        ("giant_rat", 70, 470),
        ("goblin", 175, 485),
        ("skeleton", 275, 480),
        ("orc", 380, 495),
        ("slime", 490, 515),
        ("giant", 620, 540),
        ("dragon", 800, 500),
    ]
    for mtype, mx, my in monsters:
        sprites.draw_monster(surf, mtype, mx, my, TILE, t, attacking=0.3 if mtype == "goblin" else 0.0)

    # Items / weapons strip
    _label(surf, "Items / weapons", 20, 580)
    items_db = {
        "coins": {"type": "misc"},
        "bronze_sword": {"type": "weapon"},
        "steel_sword": {"type": "weapon"},
        "mithril_scimitar": {"type": "weapon"},
        "wooden_shield": {"type": "shield", "equip_slot": "shield"},
        "iron_sq_shield": {"type": "shield", "equip_slot": "shield"},
        "raw_fish": {"type": "food"},
        "logs": {"type": "log"},
        "copper_ore": {"type": "ore"},
        "iron_ore": {"type": "ore"},
    }
    for i, iid in enumerate(items_db):
        r = pygame.Rect(20 + i * 48, 605, 40, 40)
        pygame.draw.rect(surf, (50, 48, 44), r, border_radius=4)
        sprites.draw_item_icon(surf, r, iid, items_db)

    pygame.image.save(surf, path)
    print("saved", path)


def render_variant_strip(path, t=0.8):
    W, H = 1000, 420
    surf = pygame.Surface((W, H))
    _bg(surf, (30, 34, 40))
    _label(surf, "Procedural variants — trees / rocks / characters / walk cycle", 16, 10)

    draw_terrain_block(surf, 0, 40, 25, 9, "grass", t)

    for i in range(6):
        sprites.draw_tree_detailed(surf, 70 + i * 90, 160, TILE, variant=i, t=t)

    for i in range(6):
        sprites.draw_rock_detailed(surf, 70 + i * 70, 280, TILE, variant=i, ore_type=["copper_rock", "tin_rock", "iron_rock", None, "coal_rock", "mithril_rock"][i])

    # Walk cycle frames
    for i in range(8):
        sprites.draw_humanoid_detailed(
            surf, 60 + i * 70, 370, TILE,
            body_color=(55, 130, 70), moving=True, t=i * 0.12,
            equipment={"weapon": "steel_sword"},
        )

    pygame.image.save(surf, path)
    print("saved", path)


def render_closeup(path, t=0.5):
    W, H = 800, 500
    surf = pygame.Surface((W, H))
    _bg(surf, (40, 44, 48))
    _label(surf, "Close-up — character / tree / rock / building construction", 16, 10)
    draw_terrain_block(surf, 0, 40, 20, 11, "grass", t)

    sprites.set_render_profile(tile_size=TILE, art=1.0, character=3.2, object_=3.0, monster=2.8, tree=1.8)
    sprites.draw_humanoid_detailed(
        surf, 160, 320, TILE,
        body_color=(55, 130, 70), moving=True, t=t,
        equipment={"weapon": "steel_sword", "shield": "iron_sq_shield", "helmet": "steel_helmet", "body": "steel_platebody"},
    )
    sprites.draw_tree_detailed(surf, 380, 280, TILE, variant=1, t=t)
    sprites.draw_rock_detailed(surf, 560, 340, TILE, variant=2, ore_type="iron_rock")
    sprites.draw_house(surf, (620, 160, 150, 140), style=0, t=t)
    sprites.set_render_profile(tile_size=TILE, art=1.0, character=2.5, object_=2.55, monster=2.5, tree=1.72)

    pygame.image.save(surf, path)
    print("saved", path)


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(OUT, exist_ok=True)
    sprites.set_render_profile(tile_size=TILE, art=1.0, character=2.5, object_=2.55, monster=2.5, pet=1.65, tree=1.72)

    render_world_plate(os.path.join(OUT, "showcase_world.png"))
    render_variant_strip(os.path.join(OUT, "showcase_variants.png"))
    render_closeup(os.path.join(OUT, "showcase_closeup.png"))
    print("done")


if __name__ == "__main__":
    main()
